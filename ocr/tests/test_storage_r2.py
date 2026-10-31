"""Offline storage contract tests; run with unittest without database fixtures."""

import asyncio
import io
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, unquote, urlparse

from botocore.exceptions import ClientError
from core import storage
from core.storage_config import storage_options


def settings(**overrides):
    values = dict(
        storage_provider="r2",
        minio_endpoint="http://minio:9000", minio_access_key="legacy-access",
        minio_secret_key="legacy-secret", minio_uploads_bucket="old-documents",
        minio_verify_ssl=True,
        r2_endpoint="https://0123456789abcdef0123456789abcdef.eu.r2.cloudflarestorage.com/",
        r2_access_key_id="test-r2-access", r2_secret_access_key="test-r2-secret",
        r2_bucket="private-documents",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class StorageConfigTests(unittest.TestCase):
    def options(self, **overrides):
        return storage_options(settings(**overrides), legacy_bucket="old-documents")

    def test_pydantic_loads_r2_environment_and_keeps_minio_default(self):
        from core.config import Settings
        required = dict(ocr_server_database_url="postgresql://test/test", redis_url="redis://localhost", openai_api_base_url="http://localhost", default_models="test")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Settings(_env_file=None, **required).storage_provider, "minio")
        with patch.dict(os.environ, {"STORAGE_PROVIDER": "r2", "R2_BUCKET": "private-documents", "R2_ENDPOINT": settings().r2_endpoint}, clear=True):
            configured = Settings(_env_file=None, **required)
            self.assertEqual(configured.storage_provider, "r2")
            self.assertEqual(configured.r2_bucket, "private-documents")

    def test_minio_default_options_preserve_legacy_settings(self):
        options = self.options(storage_provider="minio")
        self.assertEqual(options["endpoint_url"], "http://minio:9000")
        self.assertEqual(options["bucket_name"], "old-documents")
        self.assertEqual(options["access_key"], "legacy-access")
        self.assertEqual(options["region"], "us-east-1")
        self.assertTrue(options["ensure_bucket"])

    def test_r2_requires_eu_tls_and_isolated_credentials(self):
        options = self.options()
        self.assertTrue(options["verify_ssl"])
        self.assertFalse(options["ensure_bucket"])
        self.assertEqual(options["region"], "auto")
        self.assertEqual(options["access_key"], "test-r2-access")
        self.assertEqual(options["secret_key"], "test-r2-secret")
        self.assertEqual(options["bucket_name"], "private-documents")

    def test_missing_r2_settings_never_fall_back_to_minio(self):
        for key in ("r2_endpoint", "r2_access_key_id", "r2_secret_access_key", "r2_bucket"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.options(**{key: ""})
        with self.assertRaises(ValueError):
            self.options(storage_provider="typo")

    def test_rejects_non_eu_or_unsafe_endpoints(self):
        for endpoint in (
            "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com",
            "https://0123456789abcdef0123456789abcdef.us.r2.cloudflarestorage.com",
            "http://0123456789abcdef0123456789abcdef.eu.r2.cloudflarestorage.com",
            "https://assets.example.com",
            settings().r2_endpoint + "bucket",
            settings().r2_endpoint + "?token=secret",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                self.options(r2_endpoint=endpoint)

    def test_r2_constructor_does_not_check_or_create_buckets(self):
        client = Mock()
        with patch.object(storage.boto3, "client", return_value=client) as factory:
            storage.MinIOStorage(**self.options())
        kwargs = factory.call_args.kwargs
        self.assertTrue(kwargs["verify"])
        self.assertEqual(kwargs["config"].region_name, "auto")
        self.assertEqual(kwargs["config"].s3, {"addressing_style": "path"})
        client.head_bucket.assert_not_called()
        client.create_bucket.assert_not_called()

    def test_singleton_factory_uses_new_provider_settings(self):
        storage._storage_instance = None
        try:
            with patch("core.config.get_settings", return_value=settings()), patch.object(storage.boto3, "client"):
                instance = storage.get_storage()
                self.assertEqual(instance.bucket_name, "private-documents")
                self.assertIs(storage.get_storage(), instance)
        finally:
            storage._storage_instance = None

    def test_real_presigner_uses_eu_endpoint_auto_region_and_exact_key(self):
        instance = storage.MinIOStorage(**self.options())
        url = urlparse(asyncio.run(instance.generate_presigned_url("folder/a file.pdf", expiration=120)))
        params = parse_qs(url.query)
        self.assertEqual(url.hostname, "0123456789abcdef0123456789abcdef.eu.r2.cloudflarestorage.com")
        self.assertEqual(unquote(url.path), "/private-documents/folder/a file.pdf")
        self.assertEqual(params["X-Amz-Expires"], ["120"])
        self.assertIn("/auto/s3/aws4_request", params["X-Amz-Credential"][0])


class StorageOperationsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Mock()
        options = storage_options(settings(), legacy_bucket="old-documents")
        with patch.object(storage.boto3, "client", return_value=self.client):
            self.storage = storage.MinIOStorage(**options)

    async def test_uploads_preserve_bytes_mime_unicode_metadata_and_streaming(self):
        self.assertEqual(await self.storage.upload_file(b"pdf", "id.pdf", "application/pdf", {"name": "ҳужжат"}), "id.pdf")
        args = self.client.put_object.call_args.kwargs
        self.assertEqual(args["Bucket"], "private-documents")
        self.assertEqual(args["Body"], b"pdf")
        self.assertEqual(args["ContentType"], "application/pdf")
        self.assertNotIn("ACL", args)
        self.assertEqual(self.storage._decode_metadata_from_s3(args["Metadata"])["name"], "ҳужжат")
        file = io.BytesIO(b"streamed")
        await self.storage.upload_fileobj(file, "stream.pdf", "application/pdf")
        self.assertEqual(self.client.upload_fileobj.call_args.args, (file, "private-documents", "stream.pdf"))
        self.assertNotIn("ACL", self.client.upload_fileobj.call_args.kwargs["ExtraArgs"])

    async def test_download_head_list_and_delete_contracts(self):
        self.client.get_object.return_value = {"Body": io.BytesIO(b"original")}
        self.assertEqual(await self.storage.download_file("id.pdf"), b"original")
        self.client.head_object.return_value = {"ContentLength": 8, "ContentType": "application/pdf", "Metadata": {"name": "file"}}
        self.assertTrue(await self.storage.file_exists("id.pdf"))
        self.assertEqual((await self.storage.get_file_metadata("id.pdf"))["content_length"], 8)
        date = datetime.now(timezone.utc)
        self.client.list_objects_v2.return_value = {"Contents": [{"Key": "id.pdf", "Size": 8, "LastModified": date, "ETag": "etag"}]}
        self.assertEqual((await self.storage.list_files(prefix="id", max_keys=5))[0]["key"], "id.pdf")
        self.client.list_objects_v2.assert_called_once_with(Bucket="private-documents", Prefix="id", MaxKeys=5)
        self.assertTrue(await self.storage.delete_file("id.pdf"))
        self.client.delete_object.assert_called_once_with(Bucket="private-documents", Key="id.pdf")

    async def test_missing_and_permission_errors_are_not_confused(self):
        self.client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
        self.assertFalse(await self.storage.file_exists("missing"))
        self.assertIsNone(await self.storage.get_file_metadata("missing"))
        self.client.head_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "HeadObject")
        with self.assertRaises(ClientError):
            await self.storage.file_exists("private")


if __name__ == "__main__":
    unittest.main()
