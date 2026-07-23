from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import Config

from app.core.config import Settings, get_settings


class ObjectStorage(Protocol):
    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str: ...

    def get_bytes(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def signed_url(self, key: str, expires_in: int = 3600) -> str: ...


class LocalObjectStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        _ = content_type
        self._path(key).write_bytes(data)
        return key

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def signed_url(self, key: str, expires_in: int = 3600) -> str:
        _ = expires_in
        return f"file://{self._path(key).resolve()}"


class S3ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        addressing = "path" if settings.s3_force_path_style else "auto"
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(s3={"addressing_style": addressing}),
        )
        self.bucket = settings.s3_bucket

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        return key

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return bytes(response["Body"].read())

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def signed_url(self, key: str, expires_in: int = 3600) -> str:
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        )


def get_storage(settings: Settings | None = None) -> ObjectStorage:
    cfg = settings or get_settings()
    if cfg.storage_backend == "local":
        return LocalObjectStorage(cfg.storage_local_path)
    return S3ObjectStorage(cfg)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
