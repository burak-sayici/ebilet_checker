"""
İstasyon veri modeli.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Station:
    """Tren istasyonu"""
    
    id: int
    name: str
    pairs: list[int] = field(default_factory=list)
    ticket_sale_active: bool = True
    
    @classmethod
    def from_dict(cls, data: dict) -> "Station":
        """API yanıtından Station oluşturur"""
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            pairs=data.get("pairs", []),
            ticket_sale_active=data.get("ticketSaleActive", True)
        )
    
    def has_destination(self, station_id: int) -> bool:
        """Bu istasyondan belirtilen istasyona gidilebilir mi"""
        return station_id in self.pairs
    
    def __str__(self) -> str:
        return self.name
