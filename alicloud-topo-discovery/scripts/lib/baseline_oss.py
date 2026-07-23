#!/usr/bin/env python3
"""OSS backend for baseline management.

Stores baselines as OSS objects under {prefix}/{YYYY-MM-DD}/.
Uses aliyun ossapi or aliyun CLI if SDK not available.

Usage:
    backend = OSSBackend(bucket="my-baselines", prefix="topo/")
    key = backend.write_baseline(snapshot_path)
"""
import mimetypes
import os
import subprocess
from datetime import date
from pathlib import Path


class OSSBackend:
    """Manages baselines via OSS object storage.

    Relies on aliyun CLI for OSS operations (no oss2 SDK dependency).
    Falls back to ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET env vars.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "baselines/",
        endpoint: str | None = None,
        ak_id: str | None = None,
        ak_secret: str | None = None,
    ):
        if not bucket:
            raise ValueError("bucket must be non-empty")
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"
        self.endpoint = endpoint or os.environ.get("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")
        self.ak_id = ak_id or os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
        self.ak_secret = ak_secret or os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
        if not self.ak_id:
            raise ValueError("OSS AK ID not provided and not found in env vars")

    def write_baseline(self, snapshot: Path) -> str:
        """Upload snapshot files to OSS under {prefix}{YYYY-MM-DD}/.

        Returns the object key prefix.
        """
        today = date.today().isoformat()
        key_prefix = f"{self.prefix}{today}/"

        # Upload each file using aliyun ossapi
        for fpath in sorted(snapshot.rglob("*")):
            if fpath.is_file():
                rel = fpath.relative_to(snapshot)
                object_key = f"{key_prefix}{rel}"
                self._upload_file(str(fpath), object_key)

        # Write manifest.json last (atomicity signal)
        manifest_path = snapshot / "manifest.json"
        if manifest_path.exists():
            self._upload_file(str(manifest_path), f"{key_prefix}manifest.json")

        return key_prefix

    def list_baselines(self) -> list[date]:
        """List baseline dates from OSS prefix."""
        if not self._bucket_exists():
            return []

        objects = self._list_objects(prefix=self.prefix, delimiter="/")
        dates = []
        for obj in objects:
            # Extract date from prefix: baselines/2026-06-04/ -> 2026-06-04
            rel = obj.replace(self.prefix, "").rstrip("/")
            try:
                dates.append(date.fromisoformat(rel))
            except (ValueError, TypeError):
                continue
        return sorted(dates)

    def _upload_file(self, local_path: str, object_key: str) -> None:
        """Upload a single file to OSS using aliyun ossapi."""
        content_type, _ = mimetypes.guess_type(local_path)
        cmd = [
            "aliyun", "oss", "cp",
            local_path,
            f"oss://{self.bucket}/{object_key}",
            "--force",
        ]
        if content_type:
            cmd.extend(["--content-type", content_type])
        # Use env vars for auth
        env = os.environ.copy()
        env["ALIBABA_CLOUD_ACCESS_KEY_ID"] = self.ak_id
        env["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = self.ak_secret
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
        if result.returncode != 0:
            raise RuntimeError(f"OSS upload failed for {object_key}: {result.stderr}")

    def _list_objects(self, prefix: str, delimiter: str = "/") -> list[str]:
        """List OSS objects with given prefix, returning common prefixes."""
        result = subprocess.run(
            ["aliyun", "oss", "ls", f"oss://{self.bucket}/{prefix}", "-d", delimiter],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "ALIBABA_CLOUD_ACCESS_KEY_ID": self.ak_id,
                 "ALIBABA_CLOUD_ACCESS_KEY_SECRET": self.ak_secret},
        )
        if result.returncode != 0:
            return []
        # Parse output: "2025-06-04 10:00:00 0 Bytes oss://bucket/dir/"
        prefixes = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and "Bytes" in line:
                parts = line.split()
                if len(parts) >= 5:
                    prefixes.append(parts[4].replace(f"oss://{self.bucket}/", ""))
        return prefixes

    def _bucket_exists(self) -> bool:
        result = subprocess.run(
            ["aliyun", "oss", "ls", f"oss://{self.bucket}/"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "ALIBABA_CLOUD_ACCESS_KEY_ID": self.ak_id,
                 "ALIBABA_CLOUD_ACCESS_KEY_SECRET": self.ak_secret},
        )
        return result.returncode == 0
