"""Provider selection without network access or bucket provisioning."""

import re
from urllib.parse import urlparse


def storage_options(settings, *, legacy_bucket, r2_bucket_attribute="r2_bucket"):
    provider = settings.storage_provider.strip().lower()
    if provider == "minio":
        return {
            "endpoint_url": settings.minio_endpoint,
            "access_key": settings.minio_access_key,
            "secret_key": settings.minio_secret_key,
            "bucket_name": legacy_bucket,
            "region": "us-east-1",
            "verify_ssl": getattr(settings, "minio_verify_ssl", False),
            "ensure_bucket": True,
        }
    if provider != "r2":
        raise ValueError("STORAGE_PROVIDER must be minio or r2")

    def required(name):
        value = getattr(settings, name, "").strip()
        if not value:
            raise ValueError(f"Missing required environment variable: {name.upper()}")
        return value

    endpoint = urlparse(required("r2_endpoint"))
    if (
        endpoint.scheme != "https"
        or not re.fullmatch(
            r"[a-f0-9]{32}\.eu\.r2\.cloudflarestorage\.com",
            endpoint.hostname or "",
        )
        or endpoint.username or endpoint.password or endpoint.port
        or endpoint.path not in ("", "/") or endpoint.params
        or endpoint.query or endpoint.fragment
    ):
        raise ValueError("R2_ENDPOINT must be an HTTPS EU R2 account S3 API endpoint")
    bucket = required(r2_bucket_attribute)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Invalid R2 bucket name")
    return {
        "endpoint_url": f"https://{endpoint.hostname}",
        "access_key": required("r2_access_key_id"),
        "secret_key": required("r2_secret_access_key"),
        "bucket_name": bucket,
        "region": "auto",
        "verify_ssl": True,
        # A separately provisioned private bucket and object-only credentials are
        # sufficient. Never turn an object-storage request into bucket creation.
        "ensure_bucket": False,
    }
