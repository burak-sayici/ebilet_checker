"""
Monitor konfigürasyon modeli.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class MonitorConfig:
    """İzleme konfigürasyonu"""
    
    from_station_id: int
    to_station_id: int
    target_date: date
    
    # Filtreler
    selected_times: Optional[list[str]] = None  # None = tümü
    include_business: bool = False
    min_seats: int = 1
    
    # İzleme ayarları
    check_interval: int = 30 # saniye
    
    # Job ID (Otomatik atanır)
    job_id: Optional[str] = None
    
    def get_filter_summary(self) -> dict:
        """Filtre özetini döndürür"""
        return {
            "times": self.selected_times if self.selected_times else "Tümü",
            "business": "Dahil" if self.include_business else "Hariç",
            "min_seats": self.min_seats
        }
    
    def should_include_time(self, time_str: str) -> bool:
        """Belirtilen saat filtreye uyuyor mu"""
        if self.selected_times is None:
            return True
        return time_str in self.selected_times
