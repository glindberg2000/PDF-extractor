from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseParser(ABC):
    @abstractmethod
    def parse_file(self, input_path: str, config: Dict[str, Any] = None) -> List[Dict]:
        """Extract raw data from the input file."""
        pass

    @abstractmethod
    def normalize_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Normalize extracted data to a standard schema."""
        pass
