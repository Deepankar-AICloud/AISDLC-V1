"""Token encryption at rest and per-user rate limiting."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    """Fernet (AES-128-CBC + HMAC-SHA256). Supports key rotation: first key encrypts, all keys decrypt."""

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("at least one encryption key is required")
        self._fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]

    @classmethod
    def from_setting(cls, value: str, dev_key_file: Path | None = None) -> TokenCipher:
        keys = [k.strip() for k in value.split(",") if k.strip()]
        if not keys and dev_key_file is not None:
            dev_key_file.parent.mkdir(parents=True, exist_ok=True)
            if not dev_key_file.exists():
                dev_key_file.write_text(Fernet.generate_key().decode(), encoding="utf-8")
            keys = [dev_key_file.read_text(encoding="utf-8").strip()]
        return cls(keys)

    def encrypt(self, data: bytes) -> bytes:
        return self._fernets[0].encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        for f in self._fernets:
            try:
                return f.decrypt(token)
            except InvalidToken:
                continue
        raise InvalidToken("no key could decrypt the value")

    def encrypt_str(self, s: str) -> bytes:
        return self.encrypt(s.encode("utf-8"))

    def decrypt_str(self, b: bytes) -> str:
        return self.decrypt(b).decode("utf-8")


class RateLimiter:
    """Sliding one-minute window per (user, bucket). In-memory: use a shared store for multi-instance."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, bucket: str, per_minute: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[(key, bucket)]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= per_minute:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
