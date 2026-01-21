"""
TCDD API istemcisi.
Tüm API isteklerini bu sınıf üzerinden yapar.
"""
import requests
from typing import Optional, Any
from datetime import datetime, timedelta

from .token_manager import TokenManager
from ..config import config


class TCDDClient:
    """TCDD API istemcisi"""
    
    def __init__(self, token_manager: Optional[TokenManager] = None):
        self.token_manager = token_manager or TokenManager()
        self._api_params = {
            'environment': 'dev',
            'userId': '1',
        }
    
    def _get_headers(self) -> dict:
        """API istekleri için header'ları döndürür"""
        token = self.token_manager.get_token()
        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'tr',
            'Authorization': token or '',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': config.tcdd_base_url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'unit-id': '3895',
        }
    
    def get_stations(self) -> list[dict]:
        """
        Tüm istasyonları döndürür.
        
        Returns:
            İstasyon listesi (raw dict format)
        """
        url = f"{config.tcdd_cdn_url}/datas/station-pairs-INTERNET.json"
        
        try:
            response = requests.get(
                url,
                params=self._api_params,
                headers=self._get_headers(),
                timeout=config.request_timeout
            )
            
            if response.status_code != 200:
                print(f"HATA: İstasyon listesi alınamadı. Status: {response.status_code}")
                return []
            
            return response.json()
            
        except Exception as e:
            print(f"HATA: İstasyon yükleme hatası: {e}")
            return []
    
    def search_availability(
        self,
        from_station_id: int,
        from_station_name: str,
        to_station_id: int,
        to_station_name: str,
        target_date: datetime
    ) -> dict:
        """
        Bilet müsaitliğini sorgular.
        
        Returns:
            API yanıtı (raw dict format)
        """
        # API bir gün önce için 21:00'dan itibaren arar
        api_search_date = target_date - timedelta(days=1)
        date_str = api_search_date.strftime("%d-%m-%Y") + " 21:00:00"
        
        json_data = {
            'searchRoutes': [
                {
                    'departureStationId': from_station_id,
                    'departureStationName': from_station_name,
                    'arrivalStationId': to_station_id,
                    'arrivalStationName': to_station_name,
                    'departureDate': date_str,
                },
            ],
            'passengerTypeCounts': [{'id': 0, 'count': 1}],
            'searchReservation': False,
            'searchType': 'DOMESTIC',
            'blTrainTypes': ['TURISTIK_TREN'],
        }
        
        url = f"{config.tcdd_api_url}/tms/train/train-availability"
        
        try:
            response = requests.post(
                url,
                params=self._api_params,
                headers=self._get_headers(),
                json=json_data,
                timeout=config.request_timeout
            )
            
            if response.status_code == 401:
                # Token geçersiz, yenile ve tekrar dene
                self.token_manager.invalidate()
                return {"error": "Token geçersiz", "status": 401}
            
            if response.status_code != 200:
                return {"error": f"API hatası: {response.status_code}", "status": response.status_code}
            
            return response.json()
            
        except Exception as e:
            return {"error": str(e), "status": 0}
