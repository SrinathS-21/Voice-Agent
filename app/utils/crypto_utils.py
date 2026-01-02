import os
import logging
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - cryptography may be missing until installed
    Fernet = None
    InvalidToken = Exception

logger = logging.getLogger("crypto_utils")


def _get_fernet() -> Optional[object]:
    """Return a Fernet instance if CLOVER_ENCRYPTION_KEY is provided and cryptography is available."""
    key = os.getenv("CLOVER_ENCRYPTION_KEY")
    if not key:
        return None
    if Fernet is None:
        logger.error("cryptography.Fernet not available; install 'cryptography' to enable encryption")
        return None
    try:
        if isinstance(key, str):
            key_bytes = key.encode()
        else:
            key_bytes = key
        return Fernet(key_bytes)
    except Exception:
        logger.error("Invalid CLOVER_ENCRYPTION_KEY; falling back to no encryption", exc_info=True)
        return None


def encrypt_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    f = _get_fernet()
    if not f:
        return value
    try:
        token = f.encrypt(value.encode())
        return token.decode()
    except Exception:
        logger.error("Failed to encrypt value; returning plaintext", exc_info=True)
        return value


def decrypt_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    f = _get_fernet()
    if not f:
        return value
    try:
        out = f.decrypt(value.encode())
        return out.decode()
    except InvalidToken:
        return value
    except Exception:
        logger.error("Failed to decrypt value; returning original", exc_info=True)
        return value
