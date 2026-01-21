"""
Bilet kontrol servisi.
"""
from datetime import datetime, date
from typing import Optional

from ..api import TCDDClient
from ..models import Station, Train, TrainTime, MonitorConfig, SearchResult, TrainResult
from .station_service import StationService


class TicketService:
    """Bilet müsaitlik kontrolü"""
    
    def __init__(self, client: TCDDClient, station_service: StationService):
        self.client = client
        self.station_service = station_service
    
    def check_availability(self, config: MonitorConfig) -> SearchResult:
        """
        Bilet müsaitliğini kontrol eder.
        
        Args:
            config: İzleme konfigürasyonu (filtreler dahil)
        
        Returns:
            SearchResult
        """
        from_station = self.station_service.get_by_id(config.from_station_id)
        to_station = self.station_service.get_by_id(config.to_station_id)
        
        if not from_station or not to_station:
            return SearchResult.error_result("İstasyon bilgisi bulunamadı")
        
        # Tarih datetime'a çevir
        if isinstance(config.target_date, date):
            target_dt = datetime.combine(config.target_date, datetime.min.time())
        else:
            target_dt = config.target_date
        
        # API'yi sorgula
        response = self.client.search_availability(
            from_station_id=config.from_station_id,
            from_station_name=from_station.name,
            to_station_id=config.to_station_id,
            to_station_name=to_station.name,
            target_date=target_dt
        )
        
        if "error" in response:
            return SearchResult.error_result(response["error"])
        
        # Sonuçları parse et
        return self._parse_availability_response(response, config, from_station, to_station)
    
    def _parse_availability_response(
        self, 
        response: dict, 
        config: MonitorConfig,
        from_station: Station,
        to_station: Station
    ) -> SearchResult:
        """API yanıtını parse eder"""
        try:
            train_legs = response.get("trainLegs", [])
            if not train_legs:
                return SearchResult.empty_result(
                    f"{from_station.name} ➡ {to_station.name} yönüne uygun sefer bulunamadı."
                )
            
            availabilities = train_legs[0].get("trainAvailabilities", [])
            if not availabilities:
                return SearchResult.empty_result(
                    f"{from_station.name} ➡ {to_station.name} yönüne uygun sefer bulunamadı."
                )
            
            train_results = []
            
            for group in availabilities:
                trains_data = group.get("trains", [])
                
                for train_data in trains_data:
                    train = Train.from_dict(train_data)
                    if not train:
                        continue
                    
                    # Saat filtresi
                    if not config.should_include_time(train.get_departure_time_str()):
                        continue
                    
                    # Kriterlere uyan kabinleri al
                    available_cabins = train.get_available_cabins(
                        min_seats=config.min_seats,
                        include_business=config.include_business
                    )
                    
                    if available_cabins:
                        train_results.append(TrainResult(
                            train=train,
                            available_cabins=available_cabins
                        ))
            
            if not train_results:
                return SearchResult(
                    success=True,
                    message=f"{from_station.name} ➡ {to_station.name} - Kriterlere uygun yer bulunamadı.",
                    trains=[]
                )
            
            return SearchResult(
                success=True,
                message=f"{from_station.name} ➡ {to_station.name}",
                trains=train_results
            )
            
        except Exception as e:
            return SearchResult.error_result(f"Parse hatası: {e}")
    
    def get_train_times(
        self, 
        from_station_id: int, 
        to_station_id: int, 
        target_date: date
    ) -> list[TrainTime]:
        """
        Belirli bir güzergah ve tarihteki tren saatlerini döndürür.
        """
        from_station = self.station_service.get_by_id(from_station_id)
        to_station = self.station_service.get_by_id(to_station_id)
        
        if not from_station or not to_station:
            return []
        
        target_dt = datetime.combine(target_date, datetime.min.time())
        
        response = self.client.search_availability(
            from_station_id=from_station_id,
            from_station_name=from_station.name,
            to_station_id=to_station_id,
            to_station_name=to_station.name,
            target_date=target_dt
        )
        
        if "error" in response:
            return []
        
        train_times = []
        try:
            train_legs = response.get("trainLegs", [])
            if not train_legs:
                return []
            
            availabilities = train_legs[0].get("trainAvailabilities", [])
            
            for group in availabilities:
                trains_data = group.get("trains", [])
                for train_data in trains_data:
                    train = Train.from_dict(train_data)
                    if train:
                        train_times.append(TrainTime.from_train(train))
            
            # Saate göre sırala
            train_times.sort(key=lambda x: x.time)
            return train_times
            
        except Exception as e:
            print(f"Tren saatleri parse hatası: {e}")
            return []
