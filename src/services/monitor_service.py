"""
İzleme servisi (Multi-Monitor destekli).
"""
import threading
import uuid
from typing import Callable, Optional
from dataclasses import dataclass

from ..models import MonitorConfig, SearchResult
from .ticket_service import TicketService
from .station_service import StationService


@dataclass
class MonitorJob:
    """Aktif izleme işi"""
    job_id: str
    chat_id: str
    thread: threading.Thread
    stop_event: threading.Event
    config: MonitorConfig


class MonitorService:
    """İzleme yönetimi"""
    
    def __init__(self, ticket_service: TicketService, station_service: StationService):
        self.ticket_service = ticket_service
        self.station_service = station_service
        
        # UUID -> MonitorJob
        self._jobs: dict[str, MonitorJob] = {}
        
        # chat_id -> list[job_id] (Kullanıcının aktif işleri)
        self._user_jobs: dict[str, list[str]] = {}
        
        self._lock = threading.Lock()
    
    def start_monitor(
        self, 
        chat_id: str, 
        config: MonitorConfig,
        on_change: Callable[[str, SearchResult, dict], None],
        on_start: Optional[Callable[[str, MonitorConfig], None]] = None
    ) -> str:
        """
        Yeni izleme başlatır.
        
        Returns:
            job_id (UUID string)
        """
        job_id = str(uuid.uuid4())
        config.job_id = job_id
        
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._monitoring_loop,
            args=(chat_id, job_id, config, stop_event, on_change),
            daemon=True
        )
        
        with self._lock:
            self._jobs[job_id] = MonitorJob(
                job_id=job_id,
                chat_id=chat_id,
                thread=thread,
                stop_event=stop_event,
                config=config
            )
            
            if chat_id not in self._user_jobs:
                self._user_jobs[chat_id] = []
            self._user_jobs[chat_id].append(job_id)
        
        thread.start()
        
        if on_start:
            on_start(chat_id, config)
        
        print(f"Yeni izleme başlatıldı: {job_id} (Chat: {chat_id})")
        return job_id
    
    def stop_monitor(self, job_id: str) -> bool:
        """
        İzlemeyi durdurur (Job ID ile).
        """
        with self._lock:
            if job_id not in self._jobs:
                return False
            
            job = self._jobs[job_id]
            chat_id = job.chat_id
            
            # Thread'i durdur
            job.stop_event.set()
            
            # Listelerden temizle
            del self._jobs[job_id]
            if chat_id in self._user_jobs:
                if job_id in self._user_jobs[chat_id]:
                    self._user_jobs[chat_id].remove(job_id)
        
        print(f"İzleme durduruldu: {job_id}")
        return True
    
    def stop_all_for_user(self, chat_id: str) -> int:
        """Kullanıcının tüm izlemelerini durdurur"""
        stopped_count = 0
        with self._lock:
            if chat_id not in self._user_jobs:
                return 0
                
            # Kopyasını alıp üzerinde dönüyoruz çünkü liste değişecek
            job_ids = list(self._user_jobs[chat_id])
            
        for job_id in job_ids:
            if self.stop_monitor(job_id):
                stopped_count += 1
                
        return stopped_count
    
    def get_user_monitors(self, chat_id: str) -> list[MonitorConfig]:
        """Kullanıcının aktif izlemelerini döndürür"""
        with self._lock:
            if chat_id not in self._user_jobs:
                return []
            
            configs = []
            for job_id in self._user_jobs[chat_id]:
                if job_id in self._jobs:
                    configs.append(self._jobs[job_id].config)
            return configs
    
    def get_job(self, job_id: str) -> Optional[MonitorJob]:
        """Job detayını döndürür"""
        return self._jobs.get(job_id)

    def _monitoring_loop(
        self, 
        chat_id: str, 
        job_id: str,
        config: MonitorConfig,
        stop_event: threading.Event,
        on_change: Callable[[str, SearchResult, dict], None]
    ):
        """İzleme döngüsü"""
        from_station = self.station_service.get_by_id(config.from_station_id)
        to_station = self.station_service.get_by_id(config.to_station_id)
        
        print(f"Monitor Loop Başladı: {job_id}")
        
        previous_state: dict[str, int] = {}
        first_check = True
        
        while not stop_event.is_set():
            # Job silindiyse döngüyü kır
            if job_id not in self._jobs:
                break

            result = self.ticket_service.check_availability(config)
            current_state = self._build_state(result)
            
            if first_check:
                # İlk kontrol - mevcut durumu bildir
                on_change(chat_id, result, {
                    "type": "first_check",
                    "has_availability": result.has_availability,
                    "job_id": job_id
                })
                previous_state = current_state.copy()
                first_check = False
            else:
                # Değişiklik kontrolü
                changes = self._detect_changes(previous_state, current_state)
                
                if changes["has_new"]:
                    changes["job_id"] = job_id
                    on_change(chat_id, result, {
                        "type": "new_availability",
                        "changes": changes,
                        "job_id": job_id
                    })
                    previous_state = current_state.copy()
                elif changes["all_gone"] and previous_state:
                    on_change(chat_id, result, {
                        "type": "all_gone",
                        "job_id": job_id
                    })
                    previous_state = {}
            
            # Bekle
            if stop_event.wait(config.check_interval):
                break
        
        print(f"Monitor Loop Bitti: {job_id}")
    
    def _build_state(self, result: SearchResult) -> dict[str, int]:
        """Sonuçtan state dictionary oluşturur"""
        state = {}
        for train_result in result.trains:
            train_name = train_result.train.name
            state[train_name] = train_result.total_seats
        return state
    
    def _detect_changes(
        self, 
        previous: dict[str, int], 
        current: dict[str, int]
    ) -> dict:
        """İki state arasındaki değişiklikleri tespit eder"""
        changes = {
            "has_new": False,
            "all_gone": False,
            "new_trains": [],
            "increased": []
        }
        
        for train_name, current_seats in current.items():
            previous_seats = previous.get(train_name, 0)
            
            if current_seats > previous_seats:
                changes["has_new"] = True
                
                if previous_seats == 0:
                    changes["new_trains"].append({
                        "name": train_name,
                        "seats": current_seats
                    })
                else:
                    changes["increased"].append({
                        "name": train_name,
                        "from": previous_seats,
                        "to": current_seats
                    })
        
        # Tümü gitti mi kontrolü
        if previous and not current:
            changes["all_gone"] = True
        
        return changes
