"""No plaintext credential fallback and no secret values in public error messages."""

import base64
import hashlib
import json
import re
from uuid import uuid4

import keyring

from job_tracker.errors import UserFacingError


class Credentials:
    SERVICE = "JobTrackerAI"
    TRUSTED = (
        "keyring.backends.Windows",
        "keyring.backends.macOS",
        "keyring.backends.SecretService",
        "keyring.backends.kwallet",
    )
    CHUNK_PREFIX = "JobTrackerAI:chunks:v1:"
    CHUNK_SIZE = 1000  # ASCII pieces stay below Windows' 2,560-byte UTF-16 blob limit.
    MAX_SECRET_BYTES = 1_000_000

    def __init__(self):
        self.memory: dict[str, str] = {}
        self.session_only: set[str] = set()

    def backend(self):
        candidate = keyring.get_keyring()
        candidates = getattr(candidate, "backends", [candidate])
        for backend in candidates:
            if type(backend).__module__.startswith(self.TRUSTED):
                return backend
        raise UserFacingError("Secure OS storage is unavailable. Use session-only credentials.")

    def chunk_info(self, raw):
        if not raw or not raw.startswith(self.CHUNK_PREFIX):
            return None
        info = json.loads(raw[len(self.CHUNK_PREFIX) :])
        if (
            not isinstance(info, dict)
            or not isinstance(info.get("generation"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", info["generation"])
            or type(info.get("count")) is not int
            or not 1 <= info["count"] <= 1400
            or not isinstance(info.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", info["sha256"])
        ):
            raise UserFacingError("Saved credentials are incomplete. Reconnect in Settings.")
        return info

    def chunk_names(self, name, info):
        return [f"{name}/chunk/{info['generation']}/{index}" for index in range(info["count"])]

    def read_saved(self, backend, name):
        raw = backend.get_password(self.SERVICE, name) or ""
        info = self.chunk_info(raw)
        if info is None:
            return raw  # Existing single-entry credentials remain readable.
        pieces = [backend.get_password(self.SERVICE, part) for part in self.chunk_names(name, info)]
        if any(not part or len(part) > self.CHUNK_SIZE for part in pieces):
            raise UserFacingError("Saved credentials are incomplete. Reconnect in Settings.")
        value = base64.b64decode("".join(pieces), validate=True)
        if (
            len(value) > self.MAX_SECRET_BYTES
            or hashlib.sha256(value).hexdigest() != info["sha256"]
        ):
            raise UserFacingError("Saved credentials are incomplete. Reconnect in Settings.")
        return value.decode("utf-8")

    def delete_chunks(self, backend, name, info):
        for part in self.chunk_names(name, info):
            if backend.get_password(self.SERVICE, part):
                backend.delete_password(self.SERVICE, part)

    def write_saved(self, backend, name, value):
        old = backend.get_password(self.SERVICE, name)
        old_info = self.chunk_info(old)
        encoded = value.encode("utf-8")
        if len(encoded) > self.MAX_SECRET_BYTES:
            raise UserFacingError("The credential cache is too large. Reconnect the account.")
        created = []
        try:
            if len(value.encode("utf-16-le")) <= 2000 and not value.startswith(self.CHUNK_PREFIX):
                raw = value
            else:
                encoded_text = base64.b64encode(encoded).decode("ascii")
                pieces = [
                    encoded_text[index : index + self.CHUNK_SIZE]
                    for index in range(0, len(encoded_text), self.CHUNK_SIZE)
                ]
                info = {
                    "generation": uuid4().hex,
                    "count": len(pieces),
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                }
                for part, piece in zip(self.chunk_names(name, info), pieces, strict=True):
                    created.append(part)
                    backend.set_password(self.SERVICE, part, piece)
                raw = self.CHUNK_PREFIX + json.dumps(info)
            # Publish the pointer only after every piece has been saved securely.
            backend.set_password(self.SERVICE, name, raw)
        except Exception:
            for part in created:
                try:
                    if backend.get_password(self.SERVICE, part):
                        backend.delete_password(self.SERVICE, part)
                except Exception:
                    pass  # Preserve the original write error, never expose secret values.
            raise
        if old_info:
            self.delete_chunks(backend, name, old_info)

    def delete_saved(self, backend, name):
        raw = backend.get_password(self.SERVICE, name)
        info = self.chunk_info(raw)
        if info:
            self.delete_chunks(backend, name, info)
        if raw:
            backend.delete_password(self.SERVICE, name)

    def get(self, name: str) -> str:
        if name in self.memory:
            return self.memory[name]
        try:
            return self.read_saved(self.backend(), name)
        except Exception:
            return ""

    def save(self, name: str, value: str, persist: bool = True):
        if not value.strip():
            raise UserFacingError("Enter a credential first.")
        if persist:
            try:
                self.write_saved(self.backend(), name, value.strip())
            except Exception as error:
                raise UserFacingError(
                    "Could not save credentials securely in the OS credential store. "
                    "Try Session only or check credential-store access."
                ) from error
            self.session_only.discard(name)
        else:
            # Replacing a persistent key with a session key must not resurrect the old key
            # at the next launch. A missing secure backend still permits session-only use.
            try:
                backend = self.backend()
            except ValueError:
                backend = None
            if backend is not None:
                try:
                    self.delete_saved(backend, name)
                except Exception as error:
                    raise UserFacingError(
                        "Could not remove the previously saved credential."
                    ) from error
            self.session_only.add(name)
        self.memory[name] = value.strip()

    def remove(self, name: str):
        try:
            backend = self.backend()
            self.delete_saved(backend, name)
        except Exception as error:
            if name not in self.session_only:
                raise UserFacingError(
                    "Could not remove the saved credential from OS storage."
                ) from error
        self.memory.pop(name, None)
        self.session_only.discard(name)
