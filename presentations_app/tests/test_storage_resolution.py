"""Tests for remote storage backend resolution."""

from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from presentations_app import storage as storage_mod

build_remote_file_storage = storage_mod.build_remote_file_storage
_resolve = storage_mod._resolve_storage_backend


class StorageBackendResolutionTests(SimpleTestCase):
    @override_settings(
        STORAGE_BACKEND="local",
        SFTP_HOST="",
        S3_BUCKET="",
    )
    def test_resolve_local_explicit(self) -> None:
        self.assertEqual(_resolve(), "local")

    @override_settings(
        STORAGE_BACKEND="auto",
        SFTP_HOST="s.example.com",
        S3_BUCKET="bucket",
    )
    def test_auto_prefers_sftp_when_host_set(self) -> None:
        self.assertEqual(_resolve(), "sftp")

    @override_settings(
        STORAGE_BACKEND="auto",
        SFTP_HOST="",
        S3_BUCKET="my-bucket",
    )
    def test_auto_s3_when_no_sftp(self) -> None:
        self.assertEqual(_resolve(), "s3")

    @override_settings(
        STORAGE_BACKEND="auto",
        SFTP_HOST="",
        S3_BUCKET="",
    )
    def test_auto_local_when_empty(self) -> None:
        self.assertEqual(_resolve(), "local")

    @override_settings(
        STORAGE_BACKEND="s3",
        SFTP_HOST="",
        S3_BUCKET="b",
    )
    def test_build_remote_s3(self) -> None:
        r = build_remote_file_storage()
        self.assertIsNotNone(r)
        self.assertEqual(r.__class__.__name__, "S3FileStorage")

    @override_settings(
        STORAGE_BACKEND="local",
    )
    def test_build_remote_none(self) -> None:
        self.assertIsNone(build_remote_file_storage())
