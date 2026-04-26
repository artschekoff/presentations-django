"""Shared S3 storage helpers (delegate to :mod:`presentations_app.storage`)."""

from __future__ import annotations

from .storage import (
    build_s3_storage,
    build_s3_storage_if_configured,
    build_sftp_file_storage,
    build_local_generation_storage,
    build_remote_file_storage,
)
from presentations_module.files.s3_file_storage import S3FileStorage

__all__ = [
    "S3FileStorage",
    "build_s3_storage",
    "build_s3_storage_if_configured",
    "build_sftp_file_storage",
    "build_local_generation_storage",
    "build_remote_file_storage",
]
