"""Stream downloads from sftp:// URIs stored in Presentation.files."""

from __future__ import annotations

import mimetypes
import os
from collections.abc import Generator
from typing import TYPE_CHECKING

from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from presentations_module.files.sftp_file_storage import SftpFileStorage

if TYPE_CHECKING:
    from django.http import HttpResponse as HttpResponseT


def sftp_file_http_response(
    _request: HttpRequest, file_path: str, *, for_head: bool
) -> "HttpResponseT":
    from presentations_app.storage import build_sftp_file_storage

    storage = build_sftp_file_storage()
    rpath = storage.sftp_path_from_uri(file_path)
    sftp = storage.get_client_for_download()
    try:
        st = sftp.stat(rpath)
    except OSError as exc:
        SftpFileStorage._close(sftp)  # noqa: SLF001
        raise Http404("SFTP file not found") from exc
    size = int(getattr(st, "st_size", 0))
    filename = os.path.basename(rpath) or "download.bin"
    content_type, _ = mimetypes.guess_type(filename)
    if for_head:
        r = HttpResponse(status=200)
        r["Content-Disposition"] = f'attachment; filename="{filename}"'
        r["Content-Length"] = str(size) if size else "0"
        if content_type:
            r["Content-Type"] = content_type
        SftpFileStorage._close(sftp)  # noqa: SLF001
        return r

    def content_iter() -> Generator[bytes, None, None]:
        f = sftp.open(rpath, "rb")
        try:
            while True:
                block = f.read(65536)
                if not block:
                    return
                yield block
        finally:
            f.close()
            SftpFileStorage._close(sftp)  # noqa: SLF001

    response = StreamingHttpResponse(
        content_iter(),
        content_type=content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    if size:
        response["Content-Length"] = str(size)
    return response
