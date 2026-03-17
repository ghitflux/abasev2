from __future__ import annotations

import re

import bcrypt
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


LEGACY_BCRYPT_PATTERN = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")


def is_legacy_bcrypt_hash(value: str | None) -> bool:
    return bool(value and LEGACY_BCRYPT_PATTERN.match(value))


def encode_legacy_bcrypt_hash(raw_hash: str) -> str:
    if not is_legacy_bcrypt_hash(raw_hash):
        raise ValueError("Legacy bcrypt hash invalido.")
    return f"{LegacyLaravelBcryptPasswordHasher.algorithm}${raw_hash}"


class LegacyLaravelBcryptPasswordHasher(BasePasswordHasher):
    algorithm = "legacy_bcrypt"

    def salt(self) -> str:
        return ""

    def encode(self, password: str, salt: str) -> str:
        if password is None:
            raise TypeError("Password must be provided.")
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        return encode_legacy_bcrypt_hash(hashed.replace("$2b$", "$2y$", 1))

    def verify(self, password: str, encoded: str) -> bool:
        raw_hash = self._unwrap(encoded)
        normalized_hash = self._normalize(raw_hash)
        return bcrypt.checkpw(password.encode(), normalized_hash.encode())

    def safe_summary(self, encoded: str) -> dict[str, str]:
        raw_hash = self._unwrap(encoded)
        return {
            "algorithm": self.algorithm,
            "hash": mask_hash(raw_hash, show=8),
        }

    def must_update(self, encoded: str) -> bool:
        return False

    def harden_runtime(self, password: str, encoded: str) -> None:
        pass

    def _unwrap(self, encoded: str) -> str:
        prefix = f"{self.algorithm}$"
        if not encoded.startswith(prefix):
            raise ValueError("Encoded legacy bcrypt hash invalido.")
        raw_hash = encoded[len(prefix):]
        if not is_legacy_bcrypt_hash(raw_hash):
            raise ValueError("Legacy bcrypt hash invalido.")
        return raw_hash

    @staticmethod
    def _normalize(raw_hash: str) -> str:
        if raw_hash.startswith("$2y$"):
            return raw_hash.replace("$2y$", "$2b$", 1)
        return raw_hash
