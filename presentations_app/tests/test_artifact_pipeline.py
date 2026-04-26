"""Unit tests for presentations_app.artifact_pipeline (pytest + pytest-django)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from presentations_app.artifact_pipeline import (
    FinalizeConfig,
    _async_finalize,
    _generation_dir,
    _is_remote_path,
    compress_pdf_ghostscript,
    finalize_presentation_artifacts,
)


@pytest.mark.parametrize(
    "path,expected",
    [
        ("S3://x", True),
        ("sftp://h/k", True),
        ("http://a/b", True),
        ("/data/file.pdf", False),
        ("C:\\a.pdf", False),
        ("", False),
    ],
)
def test_is_remote_path(path: str, expected: bool) -> None:
    assert _is_remote_path(path) is expected


def test_generation_dir_uses_base_and_id(tmp_path: Path) -> None:
    base = str(tmp_path)
    assert _generation_dir(base, "gen-1") == str(tmp_path / "gen-1")


def test_async_finalize_missing_generation_dir_returns_input_paths() -> None:
    cfg = FinalizeConfig(
        compress_pdf=False,
        zip_output=False,
        zip_delete_originals=False,
        presentations_dir="/nonexistent/base",
        remote=None,
    )
    out = async_to_sync(_async_finalize)(
        ["/a/b.txt"], generation_id="missing", cfg=cfg
    )
    assert out == ["/a/b.txt"]


def test_async_finalize_zip_creates_archive_and_optionally_removes_dir(
    tmp_path: Path,
) -> None:
    gen = "g-zip-1"
    gdir = tmp_path / gen
    gdir.mkdir()
    (gdir / "file.txt").write_text("ok", encoding="utf-8")

    cfg = FinalizeConfig(
        compress_pdf=False,
        zip_output=True,
        zip_delete_originals=True,
        presentations_dir=str(tmp_path),
        remote=None,
    )
    out = async_to_sync(_async_finalize)([], generation_id=gen, cfg=cfg)
    assert len(out) == 1
    zip_path = out[0]
    assert zip_path.endswith(".zip")
    assert Path(zip_path).is_file()
    assert not gdir.is_dir()


def test_finalize_presentation_artifacts_zip_and_patches_build_remote(
    mocker: object, settings: object, tmp_path: Path
) -> None:
    """Synchronous entrypoint: zip name, rmtree, build_remote_file_storage used once."""
    g2 = "g-zip-2"
    g2dir = tmp_path / g2
    g2dir.mkdir()
    (g2dir / "a.txt").write_text("a", encoding="utf-8")
    settings.PRESENTATIONS_DIR = str(tmp_path)
    settings.PRESENTATIONS_PDF_GS_COMPRESS = False
    settings.PRESENTATIONS_ZIP_OUTPUT = True
    settings.PRESENTATIONS_ZIP_DELETE_ORIGINALS = True
    build_remote = mocker.patch(
        "presentations_app.storage.build_remote_file_storage", return_value=None
    )
    out2 = finalize_presentation_artifacts(
        [str(g2dir / "a.txt")], generation_id=g2
    )
    build_remote.assert_called_once()
    assert out2[0].endswith(f"{g2}_bundle.zip")
    assert not g2dir.is_dir()


def test_async_finalize_no_zip_lists_files_under_gen_dir(
    tmp_path: Path,
) -> None:
    gen = "g-flat"
    gdir = tmp_path / gen
    gdir.mkdir()
    f1 = gdir / "a.txt"
    f1.write_text("a", encoding="utf-8")

    cfg = FinalizeConfig(
        compress_pdf=False,
        zip_output=False,
        zip_delete_originals=False,
        presentations_dir=str(tmp_path),
        remote=None,
    )
    out = async_to_sync(_async_finalize)([str(f1)], generation_id=gen, cfg=cfg)
    assert len(out) == 1
    assert out[0] == str(f1)


@patch("presentations_app.artifact_pipeline.subprocess.run")
def test_compress_pdf_ghostscript_replaces_in_place(
    run_mock: object, tmp_path: Path
) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_text("fake", encoding="utf-8")
    # subprocess writes to tmp; simulate by touch then replace
    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:  # noqa: ANN001
        out_arg = next(c for c in cmd if c.startswith("-sOutputFile="))
        out_path = out_arg.split("=", 1)[1]
        Path(out_path).write_text("recompressed", encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

    run_mock.side_effect = fake_run
    compress_pdf_ghostscript(str(pdf))
    assert "recompressed" in pdf.read_text(encoding="utf-8")


@patch("presentations_app.artifact_pipeline.subprocess.run")
def test_compress_pdf_ghostscript_missing_gs(
    run_mock: object, tmp_path: Path
) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_text("x", encoding="utf-8")
    run_mock.side_effect = FileNotFoundError()
    with pytest.raises(RuntimeError, match="ghostscript"):
        compress_pdf_ghostscript(str(pdf))


@patch("presentations_app.artifact_pipeline.subprocess.run")
def test_compress_pdf_ghostscript_called_process_error_propagates(
    run_mock: object, tmp_path: Path
) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_text("x", encoding="utf-8")
    err = subprocess.CalledProcessError(1, "gs", stderr=b"fail line")
    run_mock.side_effect = err
    with pytest.raises(subprocess.CalledProcessError):
        compress_pdf_ghostscript(str(pdf))


@patch("presentations_app.artifact_pipeline._iter_pdfs")
@patch("presentations_app.artifact_pipeline.compress_pdf_ghostscript")
def test_async_finalize_ghostscript_failure_wraps_in_runtime_error(
    compress_mock: object,
    iter_pdfs_mock: object,
    tmp_path: Path,
) -> None:
    gen = "g-gs-err"
    gdir = tmp_path / gen
    gdir.mkdir()
    (gdir / "a.pdf").write_text("p", encoding="utf-8")
    iter_pdfs_mock.return_value = [str(gdir / "a.pdf")]

    def boom(_: str) -> None:
        err = subprocess.CalledProcessError(1, "gs", stderr=b"stderr-msg")
        raise err

    compress_mock.side_effect = boom
    cfg = FinalizeConfig(
        compress_pdf=True,
        zip_output=False,
        zip_delete_originals=False,
        presentations_dir=str(tmp_path),
        remote=None,
    )
    with pytest.raises(RuntimeError, match="PDF compression failed"):
        async_to_sync(_async_finalize)([str(gdir / "a.pdf")], generation_id=gen, cfg=cfg)
