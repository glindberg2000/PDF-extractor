import os
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime


class ClientFileSystem:
    def __init__(self, base_path: str = "client_files"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def create_client_directory(self, client_id: int, client_name: str) -> Path:
        """Create a directory structure for a new client."""
        # Create a sanitized directory name from client name
        safe_name = "".join(
            c for c in client_name if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        client_dir = self.base_path / f"{client_id}_{safe_name}"

        # Create main directory and subdirectories
        client_dir.mkdir(parents=True, exist_ok=True)
        (client_dir / "uploads").mkdir(exist_ok=True)
        (client_dir / "processed").mkdir(exist_ok=True)
        (client_dir / "archived").mkdir(exist_ok=True)

        return client_dir

    def get_upload_path(self, client_id: int, statement_type_id: int) -> Path:
        """Get the upload path for a specific client and statement type."""
        client_dir = self._find_client_directory(client_id)
        if not client_dir:
            raise ValueError(f"Client directory not found for client_id: {client_id}")

        upload_dir = client_dir / "uploads" / str(statement_type_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    def move_to_processed(self, client_id: int, file_path: Path) -> Path:
        """Move a file from uploads to processed directory."""
        client_dir = self._find_client_directory(client_id)
        if not client_dir:
            raise ValueError(f"Client directory not found for client_id: {client_id}")

        processed_dir = client_dir / "processed"
        new_path = processed_dir / file_path.name
        shutil.move(str(file_path), str(new_path))
        return new_path

    def archive_file(self, client_id: int, file_path: Path) -> Path:
        """Move a file to the archived directory with timestamp."""
        client_dir = self._find_client_directory(client_id)
        if not client_dir:
            raise ValueError(f"Client directory not found for client_id: {client_id}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_dir = client_dir / "archived"
        new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        new_path = archived_dir / new_name
        shutil.move(str(file_path), str(new_path))
        return new_path

    def _find_client_directory(self, client_id: int) -> Optional[Path]:
        """Find the client directory by ID."""
        for dir_path in self.base_path.iterdir():
            if dir_path.is_dir() and dir_path.name.startswith(f"{client_id}_"):
                return dir_path
        return None

    def list_client_files(
        self, client_id: int, statement_type_id: Optional[int] = None
    ) -> List[Path]:
        """List all files for a client, optionally filtered by statement type."""
        client_dir = self._find_client_directory(client_id)
        if not client_dir:
            return []

        files = []
        for subdir in ["uploads", "processed"]:
            target_dir = client_dir / subdir
            if statement_type_id:
                target_dir = target_dir / str(statement_type_id)

            if target_dir.exists():
                files.extend(target_dir.glob("*"))

        return files

    def delete_client_directory(self, client_id: int) -> bool:
        """Delete a client's directory and all contents."""
        client_dir = self._find_client_directory(client_id)
        if client_dir and client_dir.exists():
            shutil.rmtree(client_dir)
            return True
        return False
