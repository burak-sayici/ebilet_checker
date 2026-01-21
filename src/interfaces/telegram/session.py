"""
Telegram kullanıcı oturum yönetimi.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Any


@dataclass
class UserSession:
    """Kullanıcı oturum durumu"""
    
    state: str = ""
    action: str = ""  # "check" veya "monitor"
    
    # İstasyon seçimi
    from_station_id: Optional[int] = None
    to_station_id: Optional[int] = None
    target_date: Optional[date] = None
    
    # Monitor seçenekleri
    available_times: list[dict] = field(default_factory=list)
    selected_times: list[str] = field(default_factory=list)
    include_business: bool = False
    min_seats: int = 1
    
    # Ek veriler
    extra: dict = field(default_factory=dict)
    
    def clear(self):
        """Oturumu sıfırlar"""
        self.state = ""
        self.action = ""
        self.from_station_id = None
        self.to_station_id = None
        self.target_date = None
        self.available_times = []
        self.selected_times = []
        self.include_business = False
        self.min_seats = 1
        self.extra = {}


class SessionManager:
    """Kullanıcı oturumlarını yönetir"""
    
    def __init__(self):
        self._sessions: dict[str, UserSession] = {}
    
    def get(self, chat_id: str) -> Optional[UserSession]:
        """Oturum getirir"""
        return self._sessions.get(chat_id)
    
    def get_or_create(self, chat_id: str) -> UserSession:
        """Oturum getirir, yoksa oluşturur"""
        if chat_id not in self._sessions:
            self._sessions[chat_id] = UserSession()
        return self._sessions[chat_id]
    
    def set(self, chat_id: str, session: UserSession):
        """Oturum kaydeder"""
        self._sessions[chat_id] = session
    
    def clear(self, chat_id: str):
        """Oturumu temizler"""
        if chat_id in self._sessions:
            del self._sessions[chat_id]
    
    def has_active_session(self, chat_id: str) -> bool:
        """Aktif oturum var mı"""
        session = self._sessions.get(chat_id)
        return session is not None and session.state != ""
