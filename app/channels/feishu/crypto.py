import base64
import hashlib
import json
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class FeishuCryptoError(ValueError):
    pass


class FeishuCrypto:
    def __init__(self, encrypt_key: str, verification_token: str) -> None:
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token

    def verify_token(self, token: str | None) -> None:
        if token != self.verification_token:
            raise FeishuCryptoError("invalid verification token")

    def decrypt_event(self, encrypted: str) -> dict[str, Any]:
        """Decrypt Feishu AES-CBC event payload."""
        aes_key = hashlib.sha256(self.encrypt_key.encode("utf-8")).digest()
        try:
            encrypted_bytes = base64.b64decode(encrypted)
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16]))
            decryptor = cipher.decryptor()
            padded = decryptor.update(encrypted_bytes) + decryptor.finalize()
            pad = padded[-1]
            decoded = padded[:-pad].decode("utf-8")
            return json.loads(decoded)
        except Exception as exc:  # noqa: BLE001
            raise FeishuCryptoError("unable to decrypt event") from exc

    def decrypt_dev_event(self, encrypted: str) -> dict[str, Any]:
        try:
            decoded = base64.b64decode(encrypted).decode("utf-8")
            return json.loads(decoded)
        except Exception as exc:  # noqa: BLE001
            raise FeishuCryptoError("unable to decrypt development event") from exc

    @property
    def key_digest(self) -> str:
        return hashlib.sha256(self.encrypt_key.encode("utf-8")).hexdigest()
