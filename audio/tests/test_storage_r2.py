import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import storage
from storage_config import storage_options


def settings(**overrides):
    values = dict(
        storage_provider="r2", minio_endpoint="http://minio:9000",
        minio_access_key="legacy", minio_secret_key="legacy-secret", audio_bucket="meeting-audio",
        r2_endpoint="https://0123456789abcdef0123456789abcdef.eu.r2.cloudflarestorage.com",
        r2_access_key_id="r2-access", r2_secret_access_key="r2-secret", r2_audio_bucket="private-audio",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class AudioStorageTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        storage._client = None

    async def test_upload_and_list_keep_private_bucket_bytes_and_metadata(self):
        storage._client = None
        client = Mock()
        date = datetime.now(timezone.utc)
        client.list_objects_v2.return_value = {"Contents": [{"Key": "meeting.webm", "Size": 5, "LastModified": date}]}
        with patch.object(storage, "get_settings", return_value=settings()), patch.object(storage.boto3, "client", return_value=client) as factory:
            self.assertEqual(await storage.upload_audio("meeting.webm", b"audio", metadata={"meeting": "1"}), "meeting.webm")
            result = await storage.list_audio(prefix="meeting", max_keys=3)
        self.assertEqual(result, [{"key": "meeting.webm", "size": 5, "last_modified": date.isoformat()}])
        client.put_object.assert_called_once_with(Bucket="private-audio", Key="meeting.webm", Body=b"audio", ContentType="audio/webm", Metadata={"meeting": "1"})
        self.assertTrue(factory.call_args.kwargs["verify"])
        self.assertEqual(factory.call_args.kwargs["config"].region_name, "auto")
        client.head_bucket.assert_not_called()
        client.create_bucket.assert_not_called()

    async def test_real_presigned_url_uses_private_eu_bucket(self):
        storage._client = None
        with patch.object(storage, "get_settings", return_value=settings()):
            url = urlparse(await storage.get_presigned_url("meeting.webm", expires=120))
        self.assertEqual(url.hostname, "0123456789abcdef0123456789abcdef.eu.r2.cloudflarestorage.com")
        self.assertEqual(url.path, "/private-audio/meeting.webm")
        self.assertEqual(parse_qs(url.query)["X-Amz-Expires"], ["120"])

    def test_minio_defaults_and_r2_failure_are_isolated(self):
        legacy = settings(storage_provider="minio")
        options = storage_options(legacy, legacy_bucket=legacy.audio_bucket, r2_bucket_attribute="r2_audio_bucket")
        self.assertFalse(options["verify_ssl"])
        self.assertTrue(options["ensure_bucket"])
        self.assertEqual(options["bucket_name"], "meeting-audio")
        for change in (
            {"r2_audio_bucket": ""}, {"r2_access_key_id": ""}, {"r2_secret_access_key": ""},
            {"r2_endpoint": "https://0123456789abcdef0123456789abcdef.us.r2.cloudflarestorage.com"},
            {"storage_provider": "typo"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                storage_options(settings(**change), legacy_bucket="meeting-audio", r2_bucket_attribute="r2_audio_bucket")


if __name__ == "__main__":
    unittest.main()
