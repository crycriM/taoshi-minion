from abc import ABC, abstractmethod
from ..models import Signal
from typing import List


class BaseProvider(ABC):
    """Extend this to plug in any signal source."""

    @abstractmethod
    def fetch_signals(self) -> List[Signal]:
        """Return the latest signals from this provider."""
        ...
