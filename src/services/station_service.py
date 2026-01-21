"""
İstasyon yönetim servisi.
"""
from typing import Optional

from ..api import TCDDClient
from ..models import Station
from ..utils import normalize_turkish


class StationService:
    """İstasyon yönetimi"""
    
    def __init__(self, client: TCDDClient):
        self.client = client
        self._stations: list[Station] = []
        self._stations_by_id: dict[int, Station] = {}
    
    @property
    def is_loaded(self) -> bool:
        """İstasyonlar yüklendi mi"""
        return len(self._stations) > 0
    
    def load_stations(self) -> bool:
        """
        İstasyonları API'den yükler.
        
        Returns:
            Başarılı mı
        """
        print("İstasyonlar yükleniyor...")
        
        raw_stations = self.client.get_stations()
        if not raw_stations:
            print("HATA: İstasyon listesi alınamadı")
            return False
        
        self._stations = []
        self._stations_by_id = {}
        
        for data in raw_stations:
            station = Station.from_dict(data)
            self._stations.append(station)
            self._stations_by_id[station.id] = station
        
        print(f"✅ {len(self._stations)} istasyon yüklendi")
        return True
    
    def get_by_id(self, station_id: int) -> Optional[Station]:
        """ID ile istasyon getirir"""
        return self._stations_by_id.get(station_id)
    
    def get_active_stations(self) -> list[Station]:
        """
        Aktif istasyonları döndürür.
        (pairs listesi dolu olanlar)
        """
        active = [s for s in self._stations if s.pairs]
        return sorted(active, key=lambda x: x.name)
    
    def get_destinations(self, from_station_id: int) -> list[Station]:
        """
        Belirli bir istasyondan gidilebilecek hedefleri döndürür.
        """
        from_station = self.get_by_id(from_station_id)
        if not from_station:
            return []
        
        destinations = []
        for dest_id in from_station.pairs:
            dest = self.get_by_id(dest_id)
            if dest:
                destinations.append(dest)
        
        return sorted(destinations, key=lambda x: x.name)
    
    def search(self, query: str, from_station_id: Optional[int] = None) -> list[Station]:
        """
        İstasyonlarda arama yapar.
        
        Args:
            query: Arama terimi
            from_station_id: Verilirse sadece bu istasyonun hedeflerinde arar
        
        Returns:
            Eşleşen istasyonlar (max 10)
        """
        query_normalized = normalize_turkish(query.strip())
        
        if from_station_id:
            stations = self.get_destinations(from_station_id)
        else:
            stations = self.get_active_stations()
        
        results = []
        for station in stations:
            station_normalized = normalize_turkish(station.name)
            if query_normalized in station_normalized:
                results.append(station)
        
        return results[:10]
