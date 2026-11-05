"""Android Keystore wrapper: AES-256-GCM encrypt/decrypt via pyjnius.

The AES key is generated inside the AndroidKeyStore the first time it is needed,
tagged with alias ``msl-cal-token-key``. The raw key material never leaves the
secure storage; we only pass it to Cipher.init() by reference.

Not importable on desktop (pyjnius / jnius is Android-only).
"""

from __future__ import annotations

KEY_ALIAS = "msl-cal-token-key"
KEYSTORE_PROVIDER = "AndroidKeyStore"
TRANSFORMATION = "AES/GCM/NoPadding"
TAG_LENGTH_BITS = 128
GCM_IV_LENGTH = 12  # Android requires exactly 12 bytes for GCM


def _get_or_create_key():
    from jnius import autoclass

    KeyStore = autoclass("java.security.KeyStore")
    ks = KeyStore.getInstance(KEYSTORE_PROVIDER)
    ks.load(None)
    if ks.containsAlias(KEY_ALIAS):
        return ks.getKey(KEY_ALIAS, None)

    KeyGenerator = autoclass("javax.crypto.KeyGenerator")
    KeyGenParameterSpecBuilder = autoclass(
        "android.security.keystore.KeyGenParameterSpec$Builder")
    KeyProperties = autoclass("android.security.keystore.KeyProperties")

    purposes = KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
    builder = KeyGenParameterSpecBuilder(KEY_ALIAS, purposes)
    builder.setBlockModes(KeyProperties.BLOCK_MODE_GCM)
    builder.setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
    builder.setKeySize(256)
    spec = builder.build()

    gen = KeyGenerator.getInstance("AES", KEYSTORE_PROVIDER)
    gen.init(spec)
    return gen.generateKey()


def encrypt(plaintext: bytes) -> tuple[bytes, bytes]:
    """Encrypt ``plaintext``; returns (iv, ciphertext). Both must be stored."""
    from jnius import autoclass

    Cipher = autoclass("javax.crypto.Cipher")
    cipher = Cipher.getInstance(TRANSFORMATION)
    cipher.init(Cipher.ENCRYPT_MODE, _get_or_create_key())
    iv = bytes(cipher.getIV())
    ct = bytes(cipher.doFinal(plaintext))
    return iv, ct


def decrypt(iv: bytes, ciphertext: bytes) -> bytes:
    from jnius import autoclass

    Cipher = autoclass("javax.crypto.Cipher")
    GCMParameterSpec = autoclass("javax.crypto.spec.GCMParameterSpec")
    cipher = Cipher.getInstance(TRANSFORMATION)
    cipher.init(Cipher.DECRYPT_MODE, _get_or_create_key(),
                GCMParameterSpec(TAG_LENGTH_BITS, iv))
    return bytes(cipher.doFinal(ciphertext))


def delete_key() -> None:
    from jnius import autoclass

    KeyStore = autoclass("java.security.KeyStore")
    ks = KeyStore.getInstance(KEYSTORE_PROVIDER)
    ks.load(None)
    if ks.containsAlias(KEY_ALIAS):
        ks.deleteEntry(KEY_ALIAS)
