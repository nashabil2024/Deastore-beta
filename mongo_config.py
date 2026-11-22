"""Resolve MongoDB connection settings without reading files or logging secrets."""

from collections.abc import Mapping


def resolve_mongo_config(environ: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    """Keep URI-only setups working and optionally use separate credentials.

    MONGO_PASSWORD_ENV names an existing environment variable containing the
    password, so a stored cloud secret can be reused without copying its value.
    All validation errors deliberately contain setting names rather than values.
    """
    mongo_url = environ.get("MONGO_URL", "")
    if not mongo_url.strip():
        raise RuntimeError("MONGO_URL wajib diatur.")

    username = environ.get("MONGO_USERNAME", "").strip()
    password = environ.get("MONGO_PASSWORD", "")
    password_env = environ.get("MONGO_PASSWORD_ENV", "").strip()

    if password_env:
        if password:
            raise RuntimeError("Gunakan hanya MONGO_PASSWORD atau MONGO_PASSWORD_ENV, bukan keduanya.")
        password = environ.get(password_env, "")
        if not password:
            raise RuntimeError("MONGO_PASSWORD_ENV harus menunjuk secret kata sandi yang tersedia.")

    if not username and not password:
        return mongo_url, {}
    if not username or not password:
        raise RuntimeError("MONGO_USERNAME dan kata sandi MongoDB wajib diatur bersama.")

    # Pass credentials to the driver instead of interpolating them into a URI.
    # In particular, preserve password whitespace and special characters exactly.
    return mongo_url, {"username": username, "password": password, "authSource": "admin"}
