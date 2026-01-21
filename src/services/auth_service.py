"""
Kullanıcı yetkilendirme servisi (SQLite tabanlı).
"""
import sqlite3
import threading
from datetime import datetime
from typing import Optional

from ..config import config


class AuthService:
    """Kullanıcı yetkilendirme yönetimi"""
    
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        
        # Cache yetkili kullanıcılar (performans için)
        self._authorized_users: set[str] = set()
        self._load_users()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        """Veritabanı tablosunu oluşturur"""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS authorized_users (
                        chat_id TEXT PRIMARY KEY,
                        authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Auth DB init hatası: {e}")
    
    def _load_users(self):
        """Yetkili kullanıcıları cache'e yükler"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM authorized_users")
            rows = cursor.fetchall()
            self._authorized_users = {row[0] for row in rows}
            conn.close()
            print(f"Yetkili kullanıcılar yüklendi: {len(self._authorized_users)}")
        except Exception as e:
            print(f"Kullanıcı listesi yüklenemedi: {e}")
    
    def is_authenticated(self, chat_id: str) -> bool:
        """Kullanıcı yetkili mi?"""
        # Şifre ayarlanmamışsa herkese açık
        if not config.bot_password:
            return True
            
        return chat_id in self._authorized_users
    
    def authenticate(self, chat_id: str, password: str) -> bool:
        """Kullanıyı doğrular ve kaydeder"""
        if not config.bot_password:
            return True
            
        if password == config.bot_password:
            self._add_user(chat_id)
            return True
        
        return False
    
    def _add_user(self, chat_id: str):
        """Kullanıcıyı DB'ye ve cache'e ekler"""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO authorized_users (chat_id) VALUES (?)", 
                    (chat_id,)
                )
                conn.commit()
                conn.close()
                self._authorized_users.add(chat_id)
                print(f"Yeni kullanıcı yetkilendirildi: {chat_id}")
            except Exception as e:
                print(f"Kullanıcı ekleme hatası: {e}")
