"""Post-process generated files: PDF (Ghostscript), zip bundle, remote upload."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

import asyncio
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from presentations_module.files import FileStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinalizeConfig:
    compress_pdf: bool
    zip_output: bool
    zip_delete_originals: bool
    presentations_dir: str
    remote: FileStorage | None


def _is_remote_path(path: str) -> bool:
    p = (path or "").lower()
    return p.startswith("s3://") or p.startswith("sftp://") or p.startswith("http://")


def _iter_pdfs(root: str) -> list[str]:
    out: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".pdf"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def compress_pdf_ghostscript(pdf_path: str) -> None:
    """
    In-place recompress a PDF using the same gs flags as scripts/compress-pdf.sh
    (screen / extreme compression for size).
    """
    tmp = pdf_path + ".gs-tmp"
    try:
        subprocess.run(
            [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/screen",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={tmp}",
                pdf_path,
            ],
            check=True,
            capture_output=True,
            timeout=600,
        )
        os.replace(tmp, pdf_path)
    except FileNotFoundError as exc:
        raise RuntimeError("ghostscript (gs) is not installed or not in PATH") from exc
    finally:
        if os.path.isfile(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _generation_dir(presentations_dir: str, generation_id: str) -> str:
    base = os.path.abspath(presentations_dir or os.getcwd())
    return os.path.join(base, generation_id)


def _zip_directory(gen_dir: str, generation_id: str, remove_dir: bool) -> str:
    parent = os.path.dirname(gen_dir) or "."
    base_name = os.path.join(parent, f"{generation_id}_bundle")
    created = shutil.make_archive(base_name, "zip", root_dir=gen_dir)
    if remove_dir:
        shutil.rmtree(gen_dir, ignore_errors=False)
    return created


async def _upload_locals(
    local_paths: list[str], remote: FileStorage, pres_base: str
) -> list[str]:
    pres_base = os.path.abspath(pres_base)
    out: list[str] = []
    for p in local_paths:
        ap = os.path.abspath(p)
        relp: str
        if ap == pres_base:
            relp = os.path.basename(p)
        elif not ap.startswith(pres_base + os.sep) and not ap.startswith(
            pres_base + "/"
        ):
            relp = os.path.basename(p)
        else:
            relp = os.path.relpath(ap, start=pres_base)
        parts = [x for x in relp.replace("\\", "/").split("/") if x]
        key = remote.build_path(*parts)
        out.append(await remote.save_from_local_path(key, p))
    return out


async def _async_finalize(
    file_paths: list[str],
    *,
    generation_id: str,
    cfg: FinalizeConfig,
) -> list[str] | list[Any]:
    gdir = _generation_dir(cfg.presentations_dir, generation_id)
    if not os.path.isdir(gdir):
        logger.warning("Generation dir does not exist, skip post-process: %s", gdir)
        return [p for p in file_paths if p]

    if cfg.compress_pdf:
        for pdf in _iter_pdfs(gdir):
            try:
                compress_pdf_ghostscript(pdf)
            except subprocess.CalledProcessError as exc:
                err = getattr(exc, "stderr", b"") or b""
                try:
                    err_text = err.decode("utf-8", errors="replace")
                except (AttributeError, TypeError, ValueError):
                    err_text = str(err)
                logger.error("Ghostscript failed for %s: %s", pdf, err_text)
                raise RuntimeError(f"PDF compression failed for {pdf}: {err_text!s}") from exc

    if cfg.zip_output:
        to_upload = [
            _zip_directory(gdir, generation_id, remove_dir=cfg.zip_delete_originals)
        ]
    else:
        gdir_prefix = os.path.normpath(gdir) + os.sep
        to_upload = [
            p
            for p in file_paths
            if p
            and not _is_remote_path(p)
            and os.path.isfile(p)
            and os.path.normpath(p).startswith(gdir_prefix)
        ]
        if not to_upload:
            to_upload = [
                os.path.join(gdir, f)
                for f in os.listdir(gdir)
                if os.path.isfile(os.path.join(gdir, f))
            ]

    if not cfg.remote:
        return to_upload

    have = [p for p in to_upload if p and not _is_remote_path(p) and os.path.exists(p)]
    if not have:
        return to_upload
    return await _upload_locals(
        have, cfg.remote, os.path.abspath(cfg.presentations_dir)
    )


def finalize_presentation_artifacts(
    file_paths: list[str],
    *,
    generation_id: str,
) -> list[str] | list[Any]:
    """
    Apply optional PDF recompression, optional zip, optional remote upload.
    Synchronous entrypoint for Celery (uses asyncio.run for async upload).
    """
    from presentations_app.storage import build_remote_file_storage

    pres = settings.PRESENTATIONS_DIR or os.getcwd()
    remote = build_remote_file_storage()
    cfg = FinalizeConfig(
        compress_pdf=settings.PRESENTATIONS_PDF_GS_COMPRESS,
        zip_output=settings.PRESENTATIONS_ZIP_OUTPUT,
        zip_delete_originals=settings.PRESENTATIONS_ZIP_DELETE_ORIGINALS,
        presentations_dir=pres,
        remote=remote,
    )

    async def _go() -> list[str] | list[Any]:
        return await _async_finalize(
            [p for p in file_paths if p], generation_id=generation_id, cfg=cfg
        )

    return asyncio.run(_go())
