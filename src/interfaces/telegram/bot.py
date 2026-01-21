"""
Telegram Bot ana modülü.
"""
import requests
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from .handlers import TelegramHandlers
from .session import SessionManager
from ...config import config
from ...api import TCDDClient, TokenManager
from ...services import StationService, TicketService, MonitorService, AuthService


class TelegramBot:
    """Telegram bot sınıfı"""
    
    def __init__(self):
        self.token_manager = TokenManager()
        self.client = TCDDClient(self.token_manager)
        
        self.station_service = StationService(self.client)
        self.ticket_service = TicketService(self.client, self.station_service)
        self.monitor_service = MonitorService(self.ticket_service, self.station_service)
        self.auth_service = AuthService()  # SQLite tabanlı auth
        
        self.session_manager = SessionManager()
        self.handlers = TelegramHandlers(
            station_service=self.station_service,
            ticket_service=self.ticket_service,
            monitor_service=self.monitor_service,
            auth_service=self.auth_service,
            session_manager=self.session_manager
        )
        
        self.app: Application = None
    
    def _send_message(self, chat_id: str, message: str):
        """Telegram mesajı gönderir (thread-safe)"""
        url = f'https://api.telegram.org/bot{config.telegram_token}/sendMessage'
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code == 400:
                # HTML hatası, düz metin olarak dene
                payload.pop('parse_mode')
                requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"Mesaj gönderme hatası: {e}")
    
    def run(self):
        """Botu başlatır"""
        print("🚂 TCDD Bilet Takip Botu başlatılıyor...")
        
        # Config doğrula
        config.validate()
        
        # İstasyonları yükle
        if not self.station_service.load_stations():
            print("⚠️ İstasyonlar yüklenemedi, bot yine de başlatılıyor...")
        
        # Mesaj gönderici ayarla
        self.handlers.set_message_sender(self._send_message)
        
        # Bot oluştur
        self.app = Application.builder().token(config.telegram_token).build()
        
        # Handler'ları ekle
        self.app.add_handler(CommandHandler("start", self.handlers.start_command))
        self.app.add_handler(CommandHandler("check", self.handlers.check_command))
        self.app.add_handler(CommandHandler("monitor", self.handlers.monitor_command))
        self.app.add_handler(CommandHandler("status", self.handlers.status_command))  # Yeni komut
        self.app.add_handler(CommandHandler("stop", self.handlers.stop_command))
        
        # Callback handler (stop_job pattern'i eklendi)
        self.app.add_handler(CallbackQueryHandler(
            self.handlers.button_callback,
            pattern='^(from_|to_|date_|mtime_|mbiz_|mcount_|cancel_search|stop_job_)'
        ))
        
        # Text message handler
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handlers.text_message_handler
        ))
        
        print("✅ Bot çalışıyor...")
        self.app.run_polling()
