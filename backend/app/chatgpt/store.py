import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
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
            return ChatGPTCredentials.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, credentials: ChatGPTCredentials) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path: Path | None = None
            try:
                with NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    prefix=f".{self.path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    temporary.write(credentials.model_dump_json(indent=2))
                    temporary.flush()
                    os.fsync(temporary.fileno())
                    temporary_path = Path(temporary.name)
                os.chmod(temporary_path, 0o600)
                os.replace(temporary_path, self.path)
                os.chmod(self.path, 0o600)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()

    @contextmanager
    def session_lock(self) -> Iterator[None]:
        """Serialize rotating-token operations across API and worker processes."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

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
