"""Shared S3 storage helpers."""

from __future__ import annotations

from django.conf import settings

from presentations_module.files.s3_file_storage import S3FileStorage


def build_s3_storage() -> S3FileStorage:
    """Build S3 storage from Django settings."""
    return S3FileStorage(
        bucket=settings.S3_BUCKET or "",
        prefix=settings.S3_PREFIX or "",
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        endpoint_url=settings.S3_ENDPOINT_URL,
        verify_ssl=settings.S3_VERIFY_SSL,
    )


def build_s3_storage_if_configured() -> S3FileStorage | None:
    """Build S3 storage only when bucket is configured."""
    if not settings.S3_BUCKET:
        return None
    return build_s3_storage()
