import logging
from typing import Optional, BinaryIO
import asyncio
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.client import Config
from datetime import datetime, timedelta
import urllib.parse

logger = logging.getLogger(__name__)


class MinIOStorage:
    """MinIO storage service for handling file uploads and downloads."""

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
        region: str = "us-east-1"
    ):
        """
        Initialize MinIO storage client.

        Args:
            endpoint_url: MinIO server endpoint URL
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket_name: Default bucket name
            secure: Whether to use HTTPS
            region: AWS region (default: us-east-1)
        """
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region = region

        # Initialize S3 client with MinIO configuration
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(
                signature_version='s3v4',
                region_name=self.region,
                s3={'addressing_style': 'path'}
            ),
            verify=False  # MinIO typically uses self-signed certificates
        )

        # Ensure bucket exists
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' already exists")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created bucket '{self.bucket_name}'")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    raise
            else:
                logger.error(f"Error checking bucket: {e}")
                raise

    def _encode_metadata_for_s3(self, metadata: dict) -> dict:
        """
        Encode metadata values to be ASCII-compatible for S3.
        Non-ASCII strings are URL-encoded to ensure compatibility.

        Args:
            metadata: Dictionary of metadata key-value pairs

        Returns:
            Dictionary with ASCII-compatible values
        """
        encoded_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, str):
                try:
                    # Try to encode as ASCII to check if it's already ASCII
                    value.encode('ascii')
                    encoded_metadata[key] = value
                except UnicodeEncodeError:
                    # If it contains non-ASCII characters, URL encode it
                    encoded_metadata[key] = urllib.parse.quote(value, safe='')
                    # Add a flag to indicate this value was encoded
                    encoded_metadata[f"{key}_encoded"] = "true"
            else:
                encoded_metadata[key] = str(value)
        return encoded_metadata

    async def upload_file(
        self,
        file_content: bytes,
        file_id: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload file to MinIO.

        Args:
            file_content: File content as bytes
            file_id: Unique identifier of the file (used as object key)
            content_type: MIME type of the file
            metadata: Optional metadata to attach to the object

        Returns:
            Object key (file_id) in MinIO
        """
        try:
            # Prepare metadata
            object_metadata = metadata or {}
            object_metadata['upload_timestamp'] = datetime.utcnow().isoformat()
            object_metadata['file_id'] = file_id

            # Encode metadata to be ASCII-compatible
            encoded_metadata = self._encode_metadata_for_s3(object_metadata)

            # Upload to MinIO in thread to avoid blocking event loop
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=file_id,
                Body=file_content,
                ContentType=content_type,
                Metadata=encoded_metadata
            )

            logger.info(f"Successfully uploaded file to MinIO: {file_id}")
            return file_id

        except ClientError as e:
            logger.error(f"Failed to upload file to MinIO: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {e}")
            raise

    async def upload_fileobj(
        self,
        file_obj: BinaryIO,
        file_id: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload a file-like object to MinIO without loading it into memory."""
        try:
            object_metadata = metadata or {}
            object_metadata["upload_timestamp"] = datetime.utcnow().isoformat()
            object_metadata["file_id"] = file_id

            encoded_metadata = self._encode_metadata_for_s3(object_metadata)

            await asyncio.to_thread(
                self.s3_client.upload_fileobj,
                file_obj,
                self.bucket_name,
                file_id,
                ExtraArgs={
                    "ContentType": content_type,
                    "Metadata": encoded_metadata,
                },
            )

            logger.info(f"Successfully uploaded file object to MinIO: {file_id}")
            return file_id

        except ClientError as e:
            logger.error(f"Failed to upload file object to MinIO: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file object upload: {e}")
            raise

    async def download_file(self, file_id: str) -> bytes:
        """
        Download file from MinIO.

        Args:
            file_id: Unique identifier of the file (object key)

        Returns:
            File content as bytes
        """
        try:
            response = await asyncio.to_thread(
                self.s3_client.get_object,
                Bucket=self.bucket_name,
                Key=file_id
            )

            file_content = await asyncio.to_thread(response['Body'].read)
            logger.info(f"Successfully downloaded file from MinIO: {file_id}")
            return file_content

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.error(f"File not found in MinIO: {file_id}")
                raise FileNotFoundError(f"File {file_id} not found in MinIO")
            logger.error(f"Failed to download file from MinIO: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file download: {e}")
            raise

    async def delete_file(self, file_id: str) -> bool:
        """
        Delete file from MinIO.

        Args:
            file_id: Unique identifier of the file (object key)

        Returns:
            True if successful, False otherwise
        """
        try:
            await asyncio.to_thread(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=file_id
            )
            logger.info(f"Successfully deleted file from MinIO: {file_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete file from MinIO: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during file deletion: {e}")
            return False

    async def file_exists(self, file_id: str) -> bool:
        """
        Check if file exists in MinIO.

        Args:
            file_id: Unique identifier of the file (object key)

        Returns:
            True if file exists, False otherwise
        """
        try:
            await asyncio.to_thread(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=file_id
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence: {e}")
            raise

    def _decode_metadata_from_s3(self, metadata: dict) -> dict:
        """
        Decode metadata values that were URL-encoded for S3 compatibility.

        Args:
            metadata: Dictionary of metadata from S3

        Returns:
            Dictionary with decoded values
        """
        decoded_metadata = {}
        encoded_keys = set()

        # First pass: identify which keys were encoded
        for key, value in metadata.items():
            if key.endswith('_encoded') and value == 'true':
                original_key = key[:-8]  # Remove '_encoded' suffix
                encoded_keys.add(original_key)

        # Second pass: decode the values
        for key, value in metadata.items():
            if key.endswith('_encoded'):
                continue  # Skip the encoding flags
            elif key in encoded_keys:
                # This value was URL-encoded, so decode it
                decoded_metadata[key] = urllib.parse.unquote(value)
            else:
                decoded_metadata[key] = value

        return decoded_metadata

    async def get_file_metadata(self, file_id: str) -> Optional[dict]:
        """
        Get file metadata from MinIO.

        Args:
            file_id: Unique identifier of the file (object key)

        Returns:
            Dictionary containing file metadata or None if file doesn't exist
        """
        try:
            response = await asyncio.to_thread(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=file_id
            )

            raw_metadata = response.get('Metadata', {})
            decoded_metadata = self._decode_metadata_from_s3(raw_metadata)

            return {
                'content_type': response.get('ContentType'),
                'content_length': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'metadata': decoded_metadata,
                'etag': response.get('ETag')
            }

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            logger.error(f"Error getting file metadata: {e}")
            raise

    async def generate_presigned_url(
        self,
        file_id: str,
        expiration: int = 3600,
        operation: str = 'get_object'
    ) -> str:
        """
        Generate a presigned URL for file access.

        Args:
            file_id: Unique identifier of the file (object key)
            expiration: URL expiration time in seconds (default: 1 hour)
            operation: S3 operation (default: 'get_object' for download)

        Returns:
            Presigned URL string
        """
        try:
            url = await asyncio.to_thread(
                self.s3_client.generate_presigned_url,
                operation,
                Params={'Bucket': self.bucket_name, 'Key': file_id},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {file_id}")
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    async def list_files(self, prefix: str = "", max_keys: int = 1000) -> list:
        """
        List files in the bucket.

        Args:
            prefix: Optional prefix to filter files
            max_keys: Maximum number of keys to return

        Returns:
            List of file objects
        """
        try:
            response = await asyncio.to_thread(
                self.s3_client.list_objects_v2,
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )

            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag']
                    })

            return files

        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            raise


# Singleton instance
_storage_instance: Optional[MinIOStorage] = None


def get_storage() -> MinIOStorage:
    """Get or create MinIO storage instance using centralized settings."""
    global _storage_instance
    if _storage_instance is None:
        from core.config import get_settings
        settings = get_settings()
        _storage_instance = MinIOStorage(
            endpoint_url=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket_name=settings.minio_uploads_bucket,
        )
    return _storage_instance
