import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .client import ClientConfig
from ..utils.file import ensure_directory


class ClientManager:
    """Manages client operations (CRUD)."""

    def __init__(self, base_path: str = "data/clients"):
        self.base_path = Path(base_path)
        ensure_directory(self.base_path)

    def create_client(self, config: ClientConfig) -> bool:
        """Create a new client with the given configuration."""
        # Validate client name
        if not config.client_name or self.client_exists(config.client_name):
            return False

        # Create directory structure
        client_dir = self._get_client_dir(config.client_name)
        ensure_directory(client_dir)

        # Create input/output base directories
        ensure_directory(client_dir / "input")
        ensure_directory(client_dir / "output")

        # Create parser-specific input directories
        parser_dirs = [
            "amazon",
            "bofa_bank",
            "bofa_visa",
            "chase_visa",
            "wellsfargo_bank",
            "wellsfargo_mastercard",
            "wellsfargo_visa",
            "wellsfargo_bank_csv",
            "client_info",
            "first_republic_bank",
        ]

        for parser in parser_dirs:
            ensure_directory(client_dir / "input" / parser)

        # Save configuration
        return self._save_client_config(config)

    def update_client(self, config: ClientConfig) -> bool:
        """Update an existing client configuration."""
        if not self.client_exists(config.client_name):
            return False

        config.last_updated = datetime.now()
        return self._save_client_config(config)

    def get_client(self, client_name: str) -> Optional[ClientConfig]:
        """Get client configuration."""
        if not self.client_exists(client_name):
            return None

        config_path = self._get_config_path(client_name)
        try:
            with open(config_path, "r") as file:
                data = yaml.safe_load(file)
                return ClientConfig.from_dict(data)
        except Exception:
            return None

    def list_clients(self) -> List[str]:
        """List all available clients."""
        if not os.path.exists(self.base_path):
            return []

        return [
            d.name
            for d in os.scandir(self.base_path)
            if d.is_dir() and self._get_config_path(d.name).exists()
        ]

    def delete_client(self, client_name: str) -> bool:
        """Delete a client and all associated data."""
        import shutil

        if not self.client_exists(client_name):
            return False

        client_dir = self._get_client_dir(client_name)
        try:
            shutil.rmtree(client_dir)
            return True
        except Exception:
            return False

    def client_exists(self, client_name: str) -> bool:
        """Check if a client exists."""
        return self._get_config_path(client_name).exists()

    def _get_client_dir(self, client_name: str) -> Path:
        """Get client directory path."""
        return self.base_path / client_name

    def _get_config_path(self, client_name: str) -> Path:
        """Get path to client config file."""
        return self._get_client_dir(client_name) / "client_config.yaml"

    def _save_client_config(self, config: ClientConfig) -> bool:
        """Save client configuration to file."""
        config_path = self._get_config_path(config.client_name)
        try:
            with open(config_path, "w") as file:
                yaml.dump(config.to_dict(), file, default_flow_style=False)
            return True
        except Exception:
            return False
