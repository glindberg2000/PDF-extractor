from abc import ABC, abstractmethod
from typing import Any, Dict, List
from dataextractai.utils.data_transformation import normalize_transaction_amount


class BaseParser(ABC):
    def _normalize_amount(
        self, amount: float, transaction_type: str, is_charge_positive: bool = False
    ) -> float:
        """
        Provides a standardized way for parsers to normalize transaction amounts.
        This is a concrete helper method available to all subclasses.
        """
        return normalize_transaction_amount(
            amount, transaction_type, is_charge_positive
        )

    @abstractmethod
    def parse_file(self, input_path: str, config: Dict[str, Any] = None) -> List[Dict]:
        """Extract raw data from the input file."""
        pass

    @abstractmethod
    def normalize_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Normalize extracted data to a standard schema."""
        pass
