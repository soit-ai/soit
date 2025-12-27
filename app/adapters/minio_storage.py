""" minio_storage

MinIO/S3 storage gateway adapter implementation.
"""

from typing import Optional, Dict, Any
import boto3
from botocore.client import Config

from app.kernel.gateways.storage.interface import StorageGateway
from app.kernel.config.settings import settings


class MinIOStorageGateway(StorageGateway):
    """MinIO/S3 storage gateway adapter."""
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: Optional[bool] = None,
    ):
        """Initialize MinIO gateway.
        
        Args:
            endpoint: MinIO endpoint.
            access_key: Access key.
            secret_key: Secret key.
            bucket: Default bucket.
            secure: Use HTTPS.
        """
        self.endpoint = endpoint or settings.minio_endpoint
        self.access_key = access_key or settings.minio_access_key
        self.secret_key = secret_key or settings.minio_secret_key
        self.bucket = bucket or settings.minio_bucket
        self.secure = secure if secure is not None else settings.minio_secure
        
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
            use_ssl=self.secure,
        )
    
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Upload object.
        
        Args:
            key: Storage key (path).
            data: Object data.
            content_type: Optional content type.
            metadata: Optional metadata.
            **kwargs: Additional parameters.
            
        Returns:
            Storage key (same as input or modified).
        """
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
        
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            **extra_args,
        )
        return key
    
    async def get(
        self,
        key: str,
        **kwargs: Any,
    ) -> bytes:
        """Download object.
        
        Args:
            key: Storage key.
            **kwargs: Additional parameters.
            
        Returns:
            Object data.
        """
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()
    
    async def delete(
        self,
        key: str,
        **kwargs: Any,
    ) -> None:
        """Delete object.
        
        Args:
            key: Storage key.
            **kwargs: Additional parameters.
        """
        self.client.delete_object(Bucket=self.bucket, Key=key)
    
    async def exists(
        self,
        key: str,
        **kwargs: Any,
    ) -> bool:
        """Check if object exists.
        
        Args:
            key: Storage key.
            **kwargs: Additional parameters.
            
        Returns:
            True if exists.
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.NoSuchKey:
            return False
        except Exception:
            return False
