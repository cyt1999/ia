import base64
import hashlib
import json

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.channels.feishu.crypto import FeishuCrypto, FeishuCryptoError


def _encrypt(payload: dict, key: str) -> str:
    raw = json.dumps(payload).encode("utf-8")
    pad = 16 - (len(raw) % 16)
    padded = raw + bytes([pad]) * pad
    aes_key = hashlib.sha256(key.encode("utf-8")).digest()
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16]))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


def test_decrypt_event() -> None:
    crypto = FeishuCrypto("encrypt-key", "token")
    encrypted = _encrypt({"token": "token", "event": {"message": {}}}, "encrypt-key")

    assert crypto.decrypt_event(encrypted)["token"] == "token"


def test_invalid_token_raises() -> None:
    crypto = FeishuCrypto("encrypt-key", "token")

    with pytest.raises(FeishuCryptoError):
        crypto.verify_token("wrong")

