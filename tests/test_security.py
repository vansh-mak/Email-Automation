import pytest
from security.encryption import (
    generate_key,
    encrypt_password,
    decrypt_password,
    EncryptionError
)

def test_generate_key():
    key = generate_key()
    assert isinstance(key, str)
    assert len(key) == 44  # Standard base64-encoded 32-byte key

def test_encrypt_and_decrypt_success():
    key = generate_key()
    plaintext = "SuperSecretPassword123!"

    ciphertext = encrypt_password(plaintext, key)
    assert isinstance(ciphertext, bytes)
    assert ciphertext != plaintext.encode("utf-8")

    decrypted = decrypt_password(ciphertext, key)
    assert decrypted == plaintext

def test_empty_password_raises():
    key = generate_key()
    with pytest.raises(ValueError):
        encrypt_password("", key)

    with pytest.raises(ValueError):
        decrypt_password(b"", key)

def test_decrypt_with_wrong_key_fails():
    key1 = generate_key()
    key2 = generate_key()
    plaintext = "MyTestPassword"

    token = encrypt_password(plaintext, key1)
    with pytest.raises(EncryptionError):
        decrypt_password(token, key2)

def test_decrypt_tampered_token_fails():
    key = generate_key()
    token = bytearray(encrypt_password("TestPass", key))
    # Corrupt the payload byte
    token[-5] ^= 0xFF
    with pytest.raises(EncryptionError):
        decrypt_password(bytes(token), key)
