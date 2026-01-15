import os
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
except ImportError:
    ChaCha20Poly1305 = None

class EncryptionManager:
    """
    Optimized Encryption for Arch Linux.
    ChaCha20-Poly1305 is chosen for blazing fast software performance without AES-NI.
    """
    def __init__(self):
        key = os.getenv("SY_ENCRYPTION_KEY", "").encode().ljust(32, b'0')[:32]
        if len(key) < 32:
            key = os.urandom(32)
        self.cipher = ChaCha20Poly1305(key) if ChaCha20Poly1305 else None

    def encrypt(self, data: str) -> bytes:
        if not self.cipher: return data.encode()
        nonce = os.urandom(12)
        return nonce + self.cipher.encrypt(nonce, data.encode(), None)

    def decrypt(self, token: bytes) -> str:
        if not self.cipher: return token.decode()
        nonce, payload = token[:12], token[12:]
        return self.cipher.decrypt(nonce, payload, None).decode()