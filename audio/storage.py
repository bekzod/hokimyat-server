import asyncio
import logging
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from config import get_settings

logger = logging.getLogger(__name__)

_client = None


def _get_s3():
    global _client
    if _client is None:
        s = get_settings()
        _client = boto3.client(
            "s3",
            endpoint_url=s.minio_endpoint,
            aws_access_key_id=s.minio_access_key,
            aws_secret_access_key=s.minio_secret_key,
            config=Config(
                signature_version="s3v4",
                region_name="us-east-1",
                s3={"addressing_style": "path"},
            ),
            verify=False,
        )
        # ensure bucket
        try:
            _client.head_bucket(Bucket=s.audio_bucket)
        except ClientError:
            _client.create_bucket(Bucket=s.audio_bucket)
            logger.info("Created bucket %s", s.audio_bucket)
    return _client


def _bucket() -> str:
    return get_settings().audio_bucket


async def upload_audio(key: str, data: bytes, content_type: str = "audio/webm", metadata: Optional[dict] = None) -> str:
    s3 = _get_s3()
    await asyncio.to_thread(
        s3.put_object,
        Bucket=_bucket(),
        Key=key,
        Body=data,
        ContentType=content_type,
        Metadata=metadata or {},
    )
    logger.info("Uploaded %s (%d bytes)", key, len(data))
    return key


async def list_audio(prefix: str = "", max_keys: int = 200) -> list[dict]:
    s3 = _get_s3()
    resp = await asyncio.to_thread(
        s3.list_objects_v2,
        Bucket=_bucket(),
        Prefix=prefix,
        MaxKeys=max_keys,
    )
    files = []
    for obj in resp.get("Contents", []):
        files.append({
            "key": obj["Key"],
            "size": obj["Size"],
            "last_modified": obj["LastModified"].isoformat(),
        })
    return files


async def get_presigned_url(key: str, expires: int = 3600) -> str:
    s3 = _get_s3()
    return await asyncio.to_thread(
        s3.generate_presigned_url,
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=expires,
    )
