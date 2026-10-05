import os
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.chatgpt.models import ChatGPTCredentials


class CredentialStore:
    """Persist one local ChatGPT registration without exposing it to the browser."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = RLock()

    def load(self) -> ChatGPTCredentials | None:
        with self._lock:
            if not self.path.exists():
                return None
            return ChatGPTCredentials.model_validate_json(
                self.path.read_text(encoding="utf-8")
            )

    def save(self, credentials: ChatGPTCredentials) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            try:
                temporary.write_text(credentials.model_dump_json(indent=2), encoding="utf-8")
                os.chmod(temporary, 0o600)
                os.replace(temporary, self.path)
                os.chmod(self.path, 0o600)
            finally:
                if temporary.exists():
                    temporary.unlink()

    def ensure_host_id(self) -> ChatGPTCredentials:
        with self._lock:
            current = self.load()
            if current is not None:
                return current
            created = ChatGPTCredentials(host_id=f"urn:uuid:{uuid4()}")
            self.save(created)
            return created

    def clear_session(self) -> ChatGPTCredentials:
        with self._lock:
            current = self.ensure_host_id()
            cleared = ChatGPTCredentials(
                host_id=current.host_id,
                client_id=current.client_id,
            )
            self.save(cleared)
            return cleared
