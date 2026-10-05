from cryptography.fernet import Fernet
import os

def generate_key():
    """توليد مفتاح تشفير جديد"""
    return Fernet.generate_key().decode()

def encrypt_data(data, key):
    """تشفير البيانات نصياً"""
    if not data or not key:
        return data
    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        if isinstance(data, str):
            data = data.encode()
        return f.encrypt(data).decode()
    except Exception:
        return data

def decrypt_data(token, key):
    """فك تشفير البيانات"""
    if not token or not key:
        return token
    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.decrypt(token.encode() if isinstance(token, str) else token).decode()
    except Exception:
        return token
