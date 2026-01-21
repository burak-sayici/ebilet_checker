"""
TCDD dinamik token yönetimi.
Token'ı web sitesinden çeker ve cache'ler.
"""
import re
import requests
from typing import Optional
from datetime import datetime, timedelta

from ..config import config


class TokenManager:
    """TCDD API token yöneticisi"""
    
    def __init__(self):
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=30)
    
    def get_token(self) -> Optional[str]:
        """
        Geçerli token döndürür.
        Cache'te yoksa veya süresi dolmuşsa yeni token alır.
        """
        if self._is_token_valid():
            return self._token
        
        return self._fetch_new_token()
    
    def _is_token_valid(self) -> bool:
        """Token hala geçerli mi kontrol eder"""
        if not self._token or not self._token_expires:
            return False
        return datetime.now() < self._token_expires
    
    def _fetch_new_token(self) -> Optional[str]:
        """Web sitesinden yeni token çeker"""
        try:
            # Ana sayfayı al
            html_content = self._fetch_main_page()
            if not html_content:
                return None
            
            # JS dosya URL'ini bul
            js_url = self._extract_js_url(html_content)
            if not js_url:
                print("HATA: JS dosyası URL'i bulunamadı")
                return None
            
            # JS içeriğini al
            js_content = self._fetch_js_content(js_url)
            if not js_content:
                return None
            
            # Token'ı çıkar
            token = self._extract_token(js_content)
            if token:
                self._token = f"Bearer {token}"
                self._token_expires = datetime.now() + self._cache_duration
                print("✅ Dinamik token başarıyla alındı")
                return self._token
            
            print("HATA: Token JS içeriğinde bulunamadı")
            return None
            
        except Exception as e:
            print(f"HATA: Token alma hatası: {e}")
            return None
    
    def _fetch_main_page(self) -> Optional[str]:
        """Ana sayfayı getirir"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        try:
            response = requests.get(
                config.tcdd_base_url, 
                headers=headers, 
                timeout=config.request_timeout
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"HATA: Ana sayfa alınamadı: {e}")
            return None
    
    def _extract_js_url(self, html_content: str) -> Optional[str]:
        """HTML'den JS dosya URL'ini çıkarır"""
        match = re.search(r'src="(/js/index\.[a-f0-9]+\.js\?.*?)"', html_content)
        if match:
            return config.tcdd_base_url + match.group(1)
        return None
    
    def _fetch_js_content(self, js_url: str) -> Optional[str]:
        """JS dosyasını getirir"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        try:
            response = requests.get(js_url, headers=headers, timeout=config.request_timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"HATA: JS dosyası alınamadı: {e}")
            return None
    
    def _extract_token(self, js_content: str) -> Optional[str]:
        """JS içeriğinden token'ı çıkarır"""
        match = re.search(
            r'case\s*"TCDD-PROD":.*?["\']'
            r'(eyJh[a-zA-Z0-9\._-]+)["\']',
            js_content,
            re.DOTALL
        )
        if match:
            return match.group(1)
        return None
    
    def invalidate(self):
        """Token cache'ini temizler"""
        self._token = None
        self._token_expires = None
