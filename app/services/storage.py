"""
Storage abstraction layer — local filesystem or S3.

Switched by STORAGE_BACKEND env var:
  - "local" (default): files stay on disk at config paths
  - "s3": files are persisted to S3, local disk used as temp cache

Usage:
    from app.services.storage import storage

    storage.save("uploads/file.pdf", data)
    data = storage.load("uploads/file.pdf")
    storage.serve("output/report.xlsx", media_type, filename)
"""

import io
import os
import shutil
import logging
import tempfile
from abc import ABC, abstractmethod

from app import config

logger = logging.getLogger(__name__)


# ── Key helpers ─────────────────────────────────────────────────────────
# Keys are relative paths like "uploads/file.pdf", "jobs/abc123/job.json"
# Local paths are absolute: {BASE_DIR}/uploads/file.pdf


def _local_path(key: str) -> str:
    """Convert a storage key to an absolute local path."""
    return os.path.join(str(config.BASE_DIR), key)


def _key_from_local(local_path: str) -> str:
    """Convert an absolute local path to a storage key."""
    base = str(config.BASE_DIR)
    if local_path.startswith(base):
        return local_path[len(base):].lstrip("/")
    return local_path


# ── Abstract interface ─────────────────────────────────────────────────


class StorageBackend(ABC):
    """Abstract storage interface."""

    @abstractmethod
    def save_bytes(self, key: str, data: bytes) -> str:
        """Save bytes. Returns the local path."""
        ...

    @abstractmethod
    def save_local_file(self, local_path: str) -> str:
        """Persist a file that was already written locally (sync to remote).
        Returns the key."""
        ...

    @abstractmethod
    def load_bytes(self, key: str) -> bytes:
        """Load file contents as bytes."""
        ...

    @abstractmethod
    def ensure_local(self, key: str) -> str:
        """Ensure the file exists on local disk. Returns the local path.
        For local backend, this is a no-op. For S3, downloads if needed."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if file exists."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a file."""
        ...

    @abstractmethod
    def delete_dir(self, key_prefix: str) -> None:
        """Delete all files under a prefix (like a directory)."""
        ...

    @abstractmethod
    def list_dir(self, key_prefix: str) -> list[str]:
        """List file keys under a prefix."""
        ...

    @abstractmethod
    def get_size(self, key: str) -> int:
        """Get file size in bytes."""
        ...

    def serve(self, key: str, media_type: str, filename: str):
        """Return a FastAPI response to serve the file.
        Override in S3 backend to use presigned URLs."""
        from fastapi.responses import FileResponse
        local = self.ensure_local(key)
        return FileResponse(local, media_type=media_type, filename=filename)

    def serve_inline(self, key: str, media_type: str):
        """Return a FastAPI response to serve the file inline (e.g. PDF preview)."""
        from fastapi.responses import FileResponse
        local = self.ensure_local(key)
        return FileResponse(
            local,
            media_type=media_type,
            headers={"Content-Disposition": "inline"},
        )


# ── Local filesystem backend ──────────────────────────────────────────


class LocalStorage(StorageBackend):
    """Stores files on local disk. Default for dev."""

    def save_bytes(self, key: str, data: bytes) -> str:
        path = _local_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def save_local_file(self, local_path: str) -> str:
        # Already local — nothing to sync
        return _key_from_local(local_path)

    def load_bytes(self, key: str) -> bytes:
        path = _local_path(key)
        with open(path, "rb") as f:
            return f.read()

    def ensure_local(self, key: str) -> str:
        path = _local_path(key)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Local file not found: {path}")
        return path

    def exists(self, key: str) -> bool:
        return os.path.exists(_local_path(key))

    def delete(self, key: str) -> None:
        path = _local_path(key)
        if os.path.isfile(path):
            os.remove(path)

    def delete_dir(self, key_prefix: str) -> None:
        path = _local_path(key_prefix)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

    def list_dir(self, key_prefix: str) -> list[str]:
        path = _local_path(key_prefix)
        if not os.path.isdir(path):
            return []
        results = []
        for entry in os.listdir(path):
            results.append(f"{key_prefix.rstrip('/')}/{entry}")
        return results

    def get_size(self, key: str) -> int:
        return os.path.getsize(_local_path(key))


# ── S3 backend ────────────────────────────────────────────────────────


class S3Storage(StorageBackend):
    """
    S3-compatible storage. Files are persisted to S3 and cached locally.
    Works with AWS S3, Railway Object Store, MinIO, etc.
    """

    def __init__(self):
        import boto3

        # Railway injects: BUCKET, ACCESS_KEY_ID, SECRET_ACCESS_KEY, ENDPOINT, REGION
        # Also support explicit S3_* and AWS_* prefixed vars for other providers
        self._bucket = (
            os.getenv("S3_BUCKET")
            or os.getenv("BUCKET")
            or os.getenv("AWS_S3_BUCKET")
        )
        if not self._bucket:
            raise ValueError(
                "No S3 bucket configured. Set BUCKET (Railway), S3_BUCKET, or AWS_S3_BUCKET."
            )

        endpoint_url = (
            os.getenv("S3_ENDPOINT_URL")
            or os.getenv("ENDPOINT")
        )
        s3_kwargs = {
            "aws_access_key_id": (
                os.getenv("S3_ACCESS_KEY_ID")
                or os.getenv("ACCESS_KEY_ID")
                or os.getenv("AWS_ACCESS_KEY_ID")
            ),
            "aws_secret_access_key": (
                os.getenv("S3_SECRET_ACCESS_KEY")
                or os.getenv("SECRET_ACCESS_KEY")
                or os.getenv("AWS_SECRET_ACCESS_KEY")
            ),
            "region_name": (
                os.getenv("S3_REGION")
                or os.getenv("REGION")
                or os.getenv("AWS_DEFAULT_REGION")
                or "us-east-1"
            ),
        }
        if endpoint_url:
            s3_kwargs["endpoint_url"] = endpoint_url

        self._client = boto3.client("s3", **s3_kwargs)
        self._prefix = os.getenv("S3_PREFIX", "").rstrip("/")  # Optional key prefix

    def _s3_key(self, key: str) -> str:
        if self._prefix:
            return f"{self._prefix}/{key}"
        return key

    def save_bytes(self, key: str, data: bytes) -> str:
        # Write locally (for any immediate local reads)
        path = _local_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

        # Upload to S3
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=self._s3_key(key),
                Body=data,
            )
        except Exception as e:
            logger.error(f"S3 upload failed for {key}: {e}")
            # File is still saved locally — don't crash

        return path

    def save_local_file(self, local_path: str) -> str:
        key = _key_from_local(local_path)
        try:
            self._client.upload_file(
                local_path,
                self._bucket,
                self._s3_key(key),
            )
        except Exception as e:
            logger.error(f"S3 upload failed for {key}: {e}")
        return key

    def load_bytes(self, key: str) -> bytes:
        # Try local first
        path = _local_path(key)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                return f.read()

        # Download from S3
        response = self._client.get_object(Bucket=self._bucket, Key=self._s3_key(key))
        data = response["Body"].read()

        # Cache locally
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

        return data

    def ensure_local(self, key: str) -> str:
        path = _local_path(key)
        if os.path.isfile(path):
            return path

        # Download from S3
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._client.download_file(
                self._bucket,
                self._s3_key(key),
                path,
            )
        except Exception as e:
            logger.error(f"S3 download failed for {key}: {e}")
            raise FileNotFoundError(f"File not found: {key}") from e

        return path

    def exists(self, key: str) -> bool:
        # Check local first
        if os.path.exists(_local_path(key)):
            return True
        # Check S3
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._s3_key(key))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        # Delete local
        path = _local_path(key)
        if os.path.isfile(path):
            os.remove(path)
        # Delete from S3
        try:
            self._client.delete_object(Bucket=self._bucket, Key=self._s3_key(key))
        except Exception as e:
            logger.warning(f"S3 delete failed for {key}: {e}")

    def delete_dir(self, key_prefix: str) -> None:
        # Delete local
        path = _local_path(key_prefix)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

        # Delete from S3 (list then batch delete)
        try:
            s3_prefix = self._s3_key(key_prefix)
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=s3_prefix):
                objects = page.get("Contents", [])
                if objects:
                    self._client.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                    )
        except Exception as e:
            logger.warning(f"S3 delete_dir failed for {key_prefix}: {e}")

    def list_dir(self, key_prefix: str) -> list[str]:
        # Try local first
        local_path = _local_path(key_prefix)
        if os.path.isdir(local_path) and os.listdir(local_path):
            return [f"{key_prefix.rstrip('/')}/{entry}" for entry in os.listdir(local_path)]

        # Fall back to S3
        results = []
        try:
            s3_prefix = self._s3_key(key_prefix.rstrip("/") + "/")
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=s3_prefix):
                for obj in page.get("Contents", []):
                    # Strip the S3 prefix to get back to our key
                    s3_key = obj["Key"]
                    if self._prefix:
                        key = s3_key[len(self._prefix) + 1:]
                    else:
                        key = s3_key
                    results.append(key)
        except Exception as e:
            logger.warning(f"S3 list_dir failed for {key_prefix}: {e}")

        return results

    def get_size(self, key: str) -> int:
        path = _local_path(key)
        if os.path.isfile(path):
            return os.path.getsize(path)

        try:
            response = self._client.head_object(Bucket=self._bucket, Key=self._s3_key(key))
            return response["ContentLength"]
        except Exception:
            return 0

    def serve(self, key: str, media_type: str, filename: str):
        """For S3, use a presigned URL redirect for large files,
        or stream small files directly."""
        from fastapi.responses import RedirectResponse, FileResponse

        # If file exists locally, serve directly
        path = _local_path(key)
        if os.path.isfile(path):
            return FileResponse(path, media_type=media_type, filename=filename)

        # Generate presigned URL
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": self._s3_key(key),
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                    "ResponseContentType": media_type,
                },
                ExpiresIn=3600,
            )
            return RedirectResponse(url)
        except Exception:
            # Fallback: download and serve
            local = self.ensure_local(key)
            return FileResponse(local, media_type=media_type, filename=filename)

    def serve_inline(self, key: str, media_type: str):
        from fastapi.responses import RedirectResponse, FileResponse

        path = _local_path(key)
        if os.path.isfile(path):
            return FileResponse(path, media_type=media_type, headers={"Content-Disposition": "inline"})

        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": self._s3_key(key),
                    "ResponseContentDisposition": "inline",
                    "ResponseContentType": media_type,
                },
                ExpiresIn=3600,
            )
            return RedirectResponse(url)
        except Exception:
            local = self.ensure_local(key)
            return FileResponse(local, media_type=media_type, headers={"Content-Disposition": "inline"})


# ── Singleton ─────────────────────────────────────────────────────────

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Get the configured storage backend (lazy singleton).
    Auto-detects Railway: if BUCKET env var exists, uses S3 automatically."""
    global _storage
    if _storage is None:
        backend = os.getenv("STORAGE_BACKEND", "").lower()

        # Auto-detect: Railway sets BUCKET when an object store is linked
        if not backend:
            backend = "s3" if os.getenv("BUCKET") else "local"

        if backend == "s3":
            _storage = S3Storage()
            logger.info("Storage backend: S3 (%s)", _storage._bucket)
        else:
            _storage = LocalStorage()
            logger.info("Storage backend: local filesystem")
            # Warn if local storage is used in production (files won't survive deploys)
            if os.getenv("DATABASE_URL"):
                logger.warning(
                    "⚠️  LOCAL storage on a production host — files will be LOST on redeploy! "
                    "Link an Object Store (Railway) or set S3 env vars to persist data."
                )
    return _storage


# Convenience alias
storage = None  # Initialized lazily on first access


class _StorageProxy:
    """Lazy proxy so `from storage import store` works at import time."""
    def __getattr__(self, name):
        return getattr(get_storage(), name)


store = _StorageProxy()
