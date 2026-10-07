"""No plaintext credential fallback and no secret values in public error messages."""

import keyring


class Credentials:
    SERVICE = "JobTrackerAI"
    TRUSTED = (
        "keyring.backends.Windows",
        "keyring.backends.macOS",
        "keyring.backends.SecretService",
        "keyring.backends.kwallet",
    )

    def __init__(self):
        self.memory: dict[str, str] = {}
        self.session_only: set[str] = set()

    def backend(self):
        candidate = keyring.get_keyring()
        candidates = getattr(candidate, "backends", [candidate])
        for backend in candidates:
            if type(backend).__module__.startswith(self.TRUSTED):
                return backend
        raise ValueError("Secure OS storage is unavailable. Use session-only credentials.")

    def get(self, name: str) -> str:
        if name in self.memory:
            return self.memory[name]
        try:
            return self.backend().get_password(self.SERVICE, name) or ""
        except Exception:
            return ""

    def save(self, name: str, value: str, persist: bool = True):
        if not value.strip():
            raise ValueError("Enter a credential first.")
        if persist:
            try:
                self.backend().set_password(self.SERVICE, name, value.strip())
            except Exception as error:
                raise ValueError("Could not save securely. Try session-only storage.") from error
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
                    if backend.get_password(self.SERVICE, name):
                        backend.delete_password(self.SERVICE, name)
                except Exception as error:
                    raise ValueError("Could not remove the previously saved credential.") from error
            self.session_only.add(name)
        self.memory[name] = value.strip()

    def remove(self, name: str):
        try:
            backend = self.backend()
            if backend.get_password(self.SERVICE, name):
                backend.delete_password(self.SERVICE, name)
        except Exception as error:
            if name not in self.session_only:
                raise ValueError(
                    "Could not remove the saved credential from OS storage."
                ) from error
        self.memory.pop(name, None)
        self.session_only.discard(name)
