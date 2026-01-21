"""
Tren ve kabin veri modelleri.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Cabin:
    """Vagon/kabin sınıfı"""
    
    name: str
    available_seats: int
    min_price: float
    
    # İstenmeyen kabin tipleri
    UNWANTED_TYPES = {"TEKERLEKLİ SANDALYE", "YATAKLI", "LOCA"}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Cabin":
        """API yanıtından Cabin oluşturur"""
        return cls(
            name=data.get("cabinClass", {}).get("name", ""),
            available_seats=data.get("availabilityCount", 0),
            min_price=data.get("minPrice", 0.0)
        )
    
    def is_available(self, min_seats: int = 1) -> bool:
        """Yeterli koltuk var mı"""
        return self.available_seats >= min_seats
    
    def is_business(self) -> bool:
        """Business sınıfı mı"""
        return "BUSINESS" in self.name.upper()
    
    def is_unwanted(self) -> bool:
        """İstenmeyen kabin tipi mi"""
        return self.name.upper() in self.UNWANTED_TYPES


@dataclass
class Train:
    """Tren seferi"""
    
    name: str
    departure_time: datetime
    cabins: list[Cabin] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional["Train"]:
        """API yanıtından Train oluşturur"""
        try:
            # Kalkış zamanını parse et
            timestamp_ms = data["segments"][0]["departureTime"]
            departure_time = datetime.fromtimestamp(timestamp_ms / 1000)
            
            # Kabinleri parse et
            cabins = []
            fare_info = data.get("availableFareInfo", [{}])[0]
            cabin_classes = fare_info.get("cabinClasses", [])
            
            for cabin_data in cabin_classes:
                cabins.append(Cabin.from_dict(cabin_data))
            
            return cls(
                name=data.get("trainName", "Tren"),
                departure_time=departure_time,
                cabins=cabins
            )
        except (KeyError, IndexError, TypeError) as e:
            print(f"Train parse hatası: {e}")
            return None
    
    def get_departure_time_str(self) -> str:
        """Kalkış saatini string olarak döndürür"""
        return self.departure_time.strftime("%H:%M")
    
    def get_available_cabins(
        self, 
        min_seats: int = 1, 
        include_business: bool = True
    ) -> list[Cabin]:
        """
        Kriterlere uyan kabinleri döndürür.
        
        Args:
            min_seats: Minimum koltuk sayısı
            include_business: Business dahil mi
        """
        available = []
        for cabin in self.cabins:
            if cabin.is_unwanted():
                continue
            if not include_business and cabin.is_business():
                continue
            if cabin.is_available(min_seats):
                available.append(cabin)
        return available
    
    def has_availability(
        self, 
        min_seats: int = 1, 
        include_business: bool = True
    ) -> bool:
        """Kriterlere uyan koltuk var mı"""
        return len(self.get_available_cabins(min_seats, include_business)) > 0


@dataclass
class TrainTime:
    """Basitleştirilmiş tren saati (seçim için)"""
    
    time: str
    train_name: str
    
    @classmethod
    def from_train(cls, train: Train) -> "TrainTime":
        return cls(
            time=train.get_departure_time_str(),
            train_name=train.name
        )
