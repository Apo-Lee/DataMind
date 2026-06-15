"""AES 对称加密 — 保护数据源密码 (V2.1: HKDF 密钥派生)"""

import base64
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

# WHY: 使用 HKDF 替代简单截断/填充，确保密钥均匀分布且长度恰好 32 字节
_kdf = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,
    info=b"datamind-encryption",
)
_KEY = _kdf.derive(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(_KEY), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode()) + padder.finalize()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode()


def decrypt(encrypted: str) -> str:
    raw = base64.b64decode(encrypted.encode())
    iv, ciphertext = raw[:16], raw[16:]
    cipher = Cipher(algorithms.AES(_KEY), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode()


def safe_decrypt(encrypted: str | None, fallback: str = "") -> str:
    """安全解密，失败时返回 fallback 并记录日志"""
    if not encrypted:
        return fallback
    try:
        return decrypt(encrypted)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"解密失败，返回 fallback: {e}")
        return fallback
