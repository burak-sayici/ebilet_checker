"""
Arama sonucu modelleri.
"""
from dataclasses import dataclass, field
from typing import Optional

from .train import Train, Cabin


@dataclass
class TrainResult:
    """Tek bir trenin sonucu"""
    
    train: Train
    available_cabins: list[Cabin]
    
    @property
    def total_seats(self) -> int:
        """Toplam boş koltuk"""
        return sum(c.available_seats for c in self.available_cabins)
    
    @property
    def has_availability(self) -> bool:
        return len(self.available_cabins) > 0


@dataclass
class SearchResult:
    """Bilet arama sonucu"""
    
    success: bool
    message: str
    trains: list[TrainResult] = field(default_factory=list)
    error: Optional[str] = None
    
    @property
    def total_available_trains(self) -> int:
        """Boş yeri olan tren sayısı"""
        return sum(1 for t in self.trains if t.has_availability)
    
    @property
    def has_availability(self) -> bool:
        """Herhangi bir trende boş yer var mı"""
        return self.total_available_trains > 0
    
    @classmethod
    def error_result(cls, message: str) -> "SearchResult":
        """Hata sonucu oluşturur"""
        return cls(success=False, message=message, error=message)
    
    @classmethod
    def empty_result(cls, message: str) -> "SearchResult":
        """Boş sonuç oluşturur"""
        return cls(success=True, message=message)
