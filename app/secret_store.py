"""Keeps API keys encrypted on disk, and lets environment variables supply them instead.

Keys are encrypted with Windows' own Data Protection API (DPAPI), tied to your Windows login: someone who copies
data\\jobhunt.db to another computer or another Windows account can't read them. It is built into Windows, so nothing
extra is installed. (DPAPI doesn't protect against programs already running as you; nothing on this computer can.)

A key set as an environment variable (for example JOBHUNT_TAVILY_KEY) takes priority and is never written to disk.
"""
import base64
import ctypes
import os
import sys

PREFIX = "dpapi:"
_ENTROPY = b"JobHunt API keys v1"  # an extra app-specific secret mixed in, so other DPAPI users can't decrypt these
_UI_FORBIDDEN = 0x01  # never show a Windows prompt

# Secret name in the database -> environment variable that overrides it.
ENV_NAMES = {
    "ai_key_openrouter": "JOBHUNT_OPENROUTER_KEY",
    "ai_key_nvidia": "JOBHUNT_NVIDIA_KEY",
    "ai_key_gemini": "JOBHUNT_GEMINI_KEY",
    "ai_key_openai": "JOBHUNT_OPENAI_KEY",
    "ai_key_claude": "JOBHUNT_CLAUDE_KEY",
    "tavily_key": "JOBHUNT_TAVILY_KEY",
}


class SecretError(Exception):
    pass


def from_env(name):
    """The key set as an environment variable for this secret, or ""."""
    variable = ENV_NAMES.get(name)
    return (os.environ.get(variable) or "").strip() if variable else ""


if sys.platform == "win32":
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]

    _crypt32, _kernel32 = ctypes.WinDLL("crypt32", use_last_error=True), ctypes.WinDLL("kernel32")
    _BLOB_P = ctypes.POINTER(_Blob)
    _crypt32.CryptProtectData.argtypes = [_BLOB_P, wintypes.LPCWSTR, _BLOB_P, ctypes.c_void_p, ctypes.c_void_p,
                                          wintypes.DWORD, _BLOB_P]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [_BLOB_P, ctypes.c_void_p, _BLOB_P, ctypes.c_void_p, ctypes.c_void_p,
                                            wintypes.DWORD, _BLOB_P]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p

    def _blob(data):
        buffer = ctypes.create_string_buffer(data, len(data))
        return _Blob(len(data), ctypes.cast(buffer, ctypes.c_void_p)), buffer  # keep the buffer alive with the blob

    def _run(function, data, *middle):
        data_in, _keep1 = _blob(data)
        entropy, _keep2 = _blob(_ENTROPY)
        out = _Blob()
        if not function(ctypes.byref(data_in), *middle, ctypes.byref(entropy), None, None, _UI_FORBIDDEN, ctypes.byref(out)):
            raise SecretError(f"Windows could not {'encrypt' if function is _crypt32.CryptProtectData else 'decrypt'} "
                              f"the key (error {ctypes.get_last_error()}).")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _kernel32.LocalFree(out.pbData)

    def _protect(data):
        return _run(_crypt32.CryptProtectData, data, "JobHunt API key")

    def _unprotect(data):
        return _run(_crypt32.CryptUnprotectData, data, None)

    AVAILABLE = True
else:  # JobHunt is started by run.bat on Windows; elsewhere keys stay as they are
    AVAILABLE = False


def protect(value):
    """Text to store for a key: encrypted when Windows is available, "" for no key."""
    if not value:
        return ""
    if not AVAILABLE:
        return value
    return PREFIX + base64.b64encode(_protect(value.encode("utf-8"))).decode("ascii")


def unprotect(stored):
    """The key from what was stored. Keys saved before encryption come back as they are (and get encrypted on start).

    A key encrypted by another Windows account or computer can't be read; "" is returned, as if none was saved.
    """
    if not stored or not stored.startswith(PREFIX):
        return stored or ""
    if not AVAILABLE:
        return ""
    try:
        return _unprotect(base64.b64decode(stored[len(PREFIX):])).decode("utf-8")
    except (SecretError, ValueError, UnicodeDecodeError):
        return ""


def is_protected(stored):
    return bool(stored) and stored.startswith(PREFIX)
