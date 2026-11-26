from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.config import get_settings


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_local_file(filename: str, content: bytes) -> tuple[str, str]:
    settings = get_settings()
    root = Path(settings.local_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(content)
    safe_name = "".join(char if char.isalnum() or char in "-._" else "_" for char in filename)[:180]
    path = root / f"{digest[:16]}-{safe_name}"
    path.write_bytes(content)
    return str(path), digest

