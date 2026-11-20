"""
Credential Security and Encryption Module.

HASHING vs. ENCRYPTION:
-----------------------
- Hashing (One-Way):
  Hashing algorithms (such as bcrypt, Argon2, or PBKDF2) transform plaintext into a fixed-length
  digest that CANNOT be reversed. It is used when an application only needs to VERIFY a password
  provided by a user during login without ever knowing the plaintext.

- Authenticated Encryption (Two-Way):
  Encryption algorithms (such as Fernet, which utilizes AES-128-CBC with PKCS7 padding and HMAC-SHA256
  authentication) convert plaintext into ciphertext using a secret key, and ALLOW THE ORIGINAL PLAINTEXT
  TO BE DECRYPTED using that same key.

In this browser automation application, the backend must RETRIEVE the password to fill Google/Gmail's
login forms on the user's behalf. Therefore, one-way hashing cannot be used for this workflow;
authenticated two-way encryption (Fernet) is required.
"""

from cryptography.fernet import Fernet, InvalidToken

class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""
    pass

def generate_key() -> str:
    """Generate a new url-safe base64-encoded 32-byte Fernet encryption key."""
    return Fernet.generate_key().decode("utf-8")

def encrypt_password(password: str, key: str) -> bytes:
    """
    Encrypt a plaintext password using Fernet (AES-128-CBC + HMAC-SHA256).

    Args:
        password: The plaintext password string to encrypt.
        key: The base64-encoded Fernet key.

    Returns:
        bytes: The authenticated ciphertext token.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    try:
        f = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        return f.encrypt(password.encode("utf-8"))
    except Exception as e:
        raise EncryptionError(f"Failed to encrypt password: {str(e)}") from e

def decrypt_password(token: bytes, key: str) -> str:
    """
    Decrypt an authenticated ciphertext token back to the plaintext password.

    Args:
        token: The encrypted ciphertext bytes.
        key: The base64-encoded Fernet key.

    Returns:
        str: The decrypted plaintext password.

    Raises:
        EncryptionError: If the key is invalid or the token was tampered with.
    """
    if not token:
        raise ValueError("Token cannot be empty.")
    try:
        f = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        decrypted_bytes = f.decrypt(token)
        return decrypted_bytes.decode("utf-8")
    except InvalidToken as e:
        raise EncryptionError("Invalid token or incorrect encryption key. Ciphertext may be corrupted or tampered with.") from e
    except Exception as e:
        raise EncryptionError(f"Failed to decrypt token: {str(e)}") from e
