"""File storage factory: local (generation), S3, SFTP (upload / download)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from presentations_module.files import FileStorage, S3FileStorage, SftpFileStorage
    from presentations_module.files.local_file_storage import LocalFileStorage


def build_local_generation_storage() -> "LocalFileStorage":
    """Always use local storage during browser generation; upload runs after finalize."""
    from presentations_module.files import LocalFileStorage

    return LocalFileStorage()


def build_s3_file_storage() -> "S3FileStorage":
    from presentations_module.files import S3FileStorage

    return S3FileStorage(
        bucket=settings.S3_BUCKET or "",
        prefix=settings.S3_PREFIX or "",
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        endpoint_url=settings.S3_ENDPOINT_URL,
        verify_ssl=settings.S3_VERIFY_SSL,
    )


def build_sftp_file_storage() -> "SftpFileStorage":
    from presentations_module.files import SftpFileStorage

    return SftpFileStorage(
        host=settings.SFTP_HOST or "",
        port=settings.SFTP_PORT,
        username=settings.SFTP_USER or "",
        password=settings.SFTP_PASSWORD,
        private_key_path=settings.SFTP_PRIVATE_KEY_PATH,
        base_path=settings.SFTP_BASE_PATH or "/",
        known_hosts_path=settings.SFTP_KNOWN_HOSTS,
    )


def _resolve_storage_backend() -> str:
    """Return effective backend: s3 | sftp | local."""
    raw = (getattr(settings, "STORAGE_BACKEND", None) or "auto").strip().lower()
    if raw in {"auto", ""}:
        if getattr(settings, "SFTP_HOST", None):
            return "sftp"
        if getattr(settings, "S3_BUCKET", None):
            return "s3"
        return "local"
    if raw in {"none", "local", "off", "false"}:
        return "local"
    return raw


def build_remote_file_storage() -> "FileStorage | None":
    """Post-generation upload target, or None to keep local paths in DB."""
    backend = _resolve_storage_backend()
    if backend == "sftp" and settings.SFTP_HOST:
        return build_sftp_file_storage()
    if backend == "s3" and settings.S3_BUCKET:
        return build_s3_file_storage()
    return None


# Backward-compatible names for views
def build_s3_storage() -> "S3FileStorage":
    return build_s3_file_storage()


def build_s3_storage_if_configured() -> "S3FileStorage | None":
    if not settings.S3_BUCKET:
        return None
    return build_s3_file_storage()
