"""
Uygulama konfigürasyonu - environment değişkenlerini yönetir.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Uygulama konfigürasyonu"""
    
    # Telegram
    telegram_token: str = ""
    bot_password: str = ""  # Auth için şifre
    
    # TCDD API
    tcdd_base_url: str = "https://ebilet.tcddtasimacilik.gov.tr"
    tcdd_api_url: str = "https://web-api-prod-ytp.tcddtasimacilik.gov.tr"
    tcdd_cdn_url: str = "https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr"
    
    # Monitor settings
    default_check_interval: int = 30
    request_timeout: int = 15
    
    @classmethod
    def from_env(cls) -> "Config":
        """Environment değişkenlerinden config oluşturur"""
        return cls(
            telegram_token=os.getenv("TELEGRAM_API_TOKEN", ""),
            bot_password=os.getenv("BOT_PASSWORD", ""),
        )
    
    def validate(self) -> bool:
        """Gerekli konfigürasyonların varlığını kontrol eder"""
        if not self.telegram_token:
            raise ValueError("TELEGRAM_API_TOKEN environment variable is required")
        return True


# Global config instance
config = Config.from_env()
