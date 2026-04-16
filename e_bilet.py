import requests
import json
from datetime import datetime, timedelta
import threading
import locale
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv
import os

try:
    locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'tr_TR')
    except locale.Error:
        print("Turkish locale (tr_TR) bulunamadı, varsayılan locale kullanılıyor.")

load_dotenv()

TELEGRAM_API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

monitor_jobs = {}
user_states = {}
STATIONS_DATA = []
STATIONS_BY_ID = {}

params = {
    'environment': 'dev',
    'userId': '1',
}

async def delete_messages(context: CallbackContext, chat_id: str, message_ids: list):
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            # Mesaj zaten silinmiş veya süresi dolmuş olabilir (48 saat)
            print(f"Mesaj silme hatası (ID: {msg_id}): {e}")

def send_telegram_message(message: str, chat_id: str):
    url = f'https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage'
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 400:
            print(f"HTML formatı hatası, düz metin olarak tekrar deneniyor...")
            payload.pop('parse_mode')
            retry_response = requests.post(url, data=payload, timeout=10)
            if retry_response.status_code == 200:
                print(f"Telegram mesajı (Düz Metin) {chat_id} için gönderildi.")
            else:
                print(f"Mesaj kurtarılamadı: {retry_response.text}")
        elif response.status_code == 200:
            print(f"Telegram mesajı {chat_id} için gönderildi.")
        else:
            print(f"Telegram mesajı gönderilemedi: {response.text}")
    except Exception as e:
        print(f"Telegram mesajı gönderme hatası: {e}")

def get_dynamic_token():
    base_url = "https://ebilet.tcddtasimacilik.gov.tr"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        print(f"Ana sayfa ({base_url}) alınıyor...")
        main_page_response = requests.get(base_url, headers=headers, timeout=10)
        main_page_response.raise_for_status()
        
        html_content = main_page_response.text
        js_match = re.search(r'src="(/js/index\.[a-f0-9]+\.js\?.*?)"', html_content)
        if not js_match:
            print("HATA: Ana JS dosyası HTML'de bulunamadı.")
            return None
        
        js_file_url = base_url + js_match.group(1)
        print(f"Bulunan JS dosyası: {js_file_url}")
        
        js_response = requests.get(js_file_url, headers=headers, timeout=10)
        js_response.raise_for_status()
        
        js_content = js_response.text
        token_match = re.search(
            r'case\s*"TCDD-PROD":.*?["\'](eyJh[a-zA-Z0-9\._-]+)["\']', 
            js_content, 
            re.DOTALL
        )
        
        if not token_match:
            print("HATA: 'TCDD-PROD' token'ı bulunamadı.")
            return None
            
        access_token = token_match.group(1)
        print("✅ Dinamik token başarıyla bulundu.")
        return f"Bearer {access_token}"

    except Exception as e:
        print(f"HATA: Token alma hatası: {e}")
        return None

def load_stations():
    global STATIONS_DATA, STATIONS_BY_ID
    
    dynamic_token = get_dynamic_token()
    if not dynamic_token:
        print("❌ Token alınamadı, istasyonlar yüklenemedi!")
        return False
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'tr',
        'Authorization': dynamic_token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://ebilet.tcddtasimacilik.gov.tr/',
        'unit-id': '3895',
    }
    
    url = 'https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json'
    
    try:
        print("🚂 İstasyonlar yükleniyor...")
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ İstasyon listesi alınamadı. Durum: {response.status_code}")
            return False
        
        STATIONS_DATA = response.json()
        
        for station in STATIONS_DATA:
            STATIONS_BY_ID[station['id']] = station
        
        print(f"✅ {len(STATIONS_DATA)} istasyon başarıyla yüklendi!")
        return True
        
    except Exception as e:
        print(f"❌ İstasyon yükleme hatası: {e}")
        return False

def get_station_by_id(station_id: int):
    return STATIONS_BY_ID.get(station_id)

def get_available_destinations(from_station_id: int):
    from_station = get_station_by_id(from_station_id)
    if not from_station or not from_station.get('pairs'):
        return []
    
    destinations = []
    for dest_id in from_station['pairs']:
        dest_station = get_station_by_id(dest_id)
        if dest_station:  # Hedef istasyonu varsa ekle
            destinations.append(dest_station)
    
    # İsme göre sırala
    destinations.sort(key=lambda x: x['name'])
    return destinations

def get_active_stations():
    """Varış yeri olan tüm istasyonları döndürür (pairs listesi dolu olanlar)"""
    active_stations = [
        station for station in STATIONS_DATA 
        if station.get('pairs')  # Sadece hedef istasyonları olan istasyonları dahil et
    ]
    # İsme göre sırala
    active_stations.sort(key=lambda x: x['name'])
    return active_stations

def normalize_turkish(text: str) -> str:
    """
    Türkçe karakterleri ASCII karşılıklarına dönüştürür.
    Bu sayede 'Eskisehir' yazarak 'Eskişehir' bulunabilir.
    """
    if not text:
        return ""
    
    # Trim and handle Turkish-specific casing before lowercasing
    # to avoid 'i' + combining dot issue (U+0307)
    text = text.strip().replace('İ', 'i').replace('I', 'ı')
    result = text.lower()
    
    turkish_map = {
        'ş': 's',
        'ı': 'i',
        'ğ': 'g',
        'ü': 'u',
        'ö': 'o',
        'ç': 'c',
        '\u0307': ''  # Remove combining dot if it survived anywhere
    }
    
    for turkish_char, ascii_char in turkish_map.items():
        result = result.replace(turkish_char, ascii_char)
    
    return result

def search_stations(query: str, from_station_id: int = None) -> list:
    """
    İstasyonları arar. 
    from_station_id verilirse sadece o istasyondan gidilebilecek hedefleri arar.
    Türkçe karakter duyarsız arama yapar.
    """
    query_normalized = normalize_turkish(query.strip())
    
    if from_station_id:
        # Varış istasyonlarında ara
        stations = get_available_destinations(from_station_id)
    else:
        # Kalkış istasyonlarında ara
        stations = get_active_stations()
    
    # Arama yap - normalize edilmiş karşılaştırma
    results = []
    for station in stations:
        station_name_normalized = normalize_turkish(station['name'])
        if query_normalized in station_name_normalized:
            results.append(station)
    
    # En fazla 10 sonuç döndür (Telegram buton limiti için)
    return results[:10]

def create_search_result_keyboard(stations: list, action: str, from_station_id: int = None) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    
    if from_station_id:
        prefix = f"to_{action}_{from_station_id}"
    else:
        prefix = f"from_{action}"
    
    for station in stations:
        station_name = station['name'][:25]  # Uzun isimleri kısalt
        callback_data = f"{prefix}_{station['id']}"
        
        row.append(InlineKeyboardButton(station_name, callback_data=callback_data))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # İptal butonu ekle
    keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="cancel_search")])
    
    return InlineKeyboardMarkup(keyboard)

def get_available_train_times(from_id: int, to_id: int, target_date: datetime) -> list:
    """
    Seçilen güzergah ve tarihteki tren kalkış saatlerini döndürür.
    Returns: [{"time": "08:00", "train_name": "YHT 1234"}, ...]
    """
    dynamic_token = get_dynamic_token()
    if not dynamic_token:
        return []
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'tr',
        'Authorization': dynamic_token,
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://ebilet.tcddtasimacilik.gov.tr',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'unit-id': '3895',
    }
    
    from_station = get_station_by_id(from_id)
    to_station = get_station_by_id(to_id)
    
    if not from_station or not to_station:
        return []
    
    api_search_date = target_date - timedelta(days=1)
    date_str = api_search_date.strftime("%d-%m-%Y") + " 21:00:00"
    
    json_data = {
        'searchRoutes': [
            {
                'departureStationId': from_id,
                'departureStationName': from_station['name'],
                'arrivalStationId': to_id,
                'arrivalStationName': to_station['name'],
                'departureDate': date_str,
            },
        ],
        'passengerTypeCounts': [{'id': 0, 'count': 1}],
        'searchReservation': False,
        'searchType': 'DOMESTIC',
        'blTrainTypes': ['TURISTIK_TREN'],
    }
    
    try:
        response = requests.post(
            'https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability',
            params=params,
            headers=headers,
            json=json_data,
            timeout=15
        )
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        sefer_gruplari = data.get("trainLegs", [{}])[0].get("trainAvailabilities", [])
        
        train_times = []
        for sefer_grubu in sefer_gruplari:
            trenler = sefer_grubu.get("trains", [])
            for tren in trenler:
                try:
                    timestamp_ms = tren["segments"][0]["departureTime"]
                    timestamp_sn = timestamp_ms / 1000
                    kalkis_saati = datetime.fromtimestamp(timestamp_sn).strftime("%H:%M")
                    tren_adi = tren.get("trainName", "Tren")
                    tren_tipi = tren.get("type", "Bilinmiyor")
                    train_times.append({
                        "time": kalkis_saati,
                        "train_name": tren_adi,
                        "train_type": tren_tipi
                    })
                except (KeyError, IndexError):
                    continue
        
        train_times.sort(key=lambda x: x["time"])
        return train_times
        
    except Exception as e:
        print(f"Tren saatleri alınırken hata: {e}")
        return []

def create_time_selection_keyboard(available_times: list, selected_times: list, callback_prefix: str) -> InlineKeyboardMarkup:
    """
    Saat seçim klavyesi oluşturur.
    Seçilen saatler ✅ ile işaretlenir.
    """
    keyboard = []
    row = []
    
    for train_info in available_times:
        time_str = train_info["time"]
        train_type = train_info.get("train_type", "")
        is_selected = time_str in selected_times
        
        # Tren tipini belirle
        type_display = ""
        if train_type == "YHT":
            type_display = " (YHT)"
        elif train_type == "AH":
            type_display = " (Anahat)"
        
        # Buton metni: seçiliyse ✅, değilse normal + tren tipi
        button_text = f"✅ {time_str}{type_display}" if is_selected else f"{time_str}{type_display}"
        callback_data = f"{callback_prefix}_toggle_{time_str}"
        
        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # Alt butonlar: Tümünü Seç / Seçimi Temizle ve Devam
    select_all_text = "📋 Tümünü Seç" if len(selected_times) < len(available_times) else "🔄 Seçimi Temizle"
    keyboard.append([
        InlineKeyboardButton(select_all_text, callback_data=f"{callback_prefix}_all"),
        InlineKeyboardButton("➡️ Devam", callback_data=f"{callback_prefix}_done")
    ])
    
    keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="cancel_search")])
    
    return InlineKeyboardMarkup(keyboard)

def create_business_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🪑 Sadece Ekonomi", callback_data=f"{callback_prefix}_no"),
            InlineKeyboardButton("💼 Business Dahil", callback_data=f"{callback_prefix}_yes")
        ],
        [InlineKeyboardButton("❌ İptal", callback_data="cancel_search")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_passenger_count_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("1 Kişi", callback_data=f"{callback_prefix}_1"),
            InlineKeyboardButton("2 Kişi", callback_data=f"{callback_prefix}_2"),
            InlineKeyboardButton("3 Kişi", callback_data=f"{callback_prefix}_3")
        ],
        [
            InlineKeyboardButton("4 Kişi", callback_data=f"{callback_prefix}_4"),
            InlineKeyboardButton("5 Kişi", callback_data=f"{callback_prefix}_5"),
            InlineKeyboardButton("6 Kişi", callback_data=f"{callback_prefix}_6")
        ],
        [InlineKeyboardButton("❌ İptal", callback_data="cancel_search")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_interval_selection_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("1 dk", callback_data=f"{callback_prefix}_60"),
            InlineKeyboardButton("2 dk", callback_data=f"{callback_prefix}_120"),
        ],
        [
            InlineKeyboardButton("5 dk", callback_data=f"{callback_prefix}_300"),
            InlineKeyboardButton("10 dk", callback_data=f"{callback_prefix}_600"),
        ],
        [InlineKeyboardButton("❌ İptal", callback_data="cancel_search")]
    ]
    return InlineKeyboardMarkup(keyboard)

def check_api_and_parse(from_id: int, to_id: int, target_date: datetime, 
                         selected_times: list = None, include_business: bool = True, min_seats: int = 1):
    """
    API'yi kontrol eder ve bilet durumunu parse eder.
    
    Args:
        selected_times: Sadece bu saatlerdeki trenleri kontrol et (None = hepsi)
        include_business: Business sınıfını dahil et
        min_seats: Minimum koltuk sayısı filtresi
    """
    dynamic_token = get_dynamic_token()

    if not dynamic_token:
        return (False, "❌ HATA: Dinamik Authorization Token'ı alınamadı.")

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'tr',
        'Authorization': dynamic_token,
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://ebilet.tcddtasimacilik.gov.tr',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'unit-id': '3895',
    }

    from_station = get_station_by_id(from_id)
    to_station = get_station_by_id(to_id)
    
    if not from_station or not to_station:
        return (False, "❌ HATA: İstasyon bilgisi bulunamadı.")

    api_search_date = target_date - timedelta(days=1)
    date_str = api_search_date.strftime("%d-%m-%Y") + " 21:00:00"

    json_data = {
        'searchRoutes': [
            {
                'departureStationId': from_id,
                'departureStationName': from_station['name'],
                'arrivalStationId': to_id,
                'arrivalStationName': to_station['name'],
                'departureDate': date_str,
            },
        ],
        'passengerTypeCounts': [{'id': 0, 'count': 1}],
        'searchReservation': False,
        'searchType': 'DOMESTIC',
        'blTrainTypes': ['TURISTIK_TREN'],
    }

    try:
        response = requests.post(
            'https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability',
            params=params,
            headers=headers,
            json=json_data,
            timeout=15
        )

        if response.status_code == 401:
            return (False, "❌ HATA: API Token'ı geçersiz.")
        elif response.status_code != 200:
            return (False, f"❌ HATA: API yanıtı beklenmedik. Durum: {response.status_code}")

        data = response.json()
        sefer_gruplari_listesi = data["trainLegs"][0]["trainAvailabilities"]
        
        date_tr_str = target_date.strftime("%d %B %Y")
        route_str = f"<b>{from_station['name']} ➡ {to_station['name']}</b> | <b>{date_tr_str}</b>"

        if not sefer_gruplari_listesi:
            return (False, f"ℹ️ {route_str} yönüne uygun sefer bulunamadı.")

        result_message = f"✅ <b>{route_str}</b>\n\nBulunan seferler:\n"
        
        toplam_tren_sayaci = 0
        bulunan_koltuk = False
        
        for sefer_grubu in sefer_gruplari_listesi:
            trenler_listesi = sefer_grubu.get("trains")
            if not trenler_listesi:
                continue
                
            for tren in trenler_listesi:
                toplam_tren_sayaci += 1
                tren_mesaj_taslagi = ""
                vagon_bulundu_bu_trende = False
                
                try:
                    timestamp_ms = tren["segments"][0]["departureTime"]
                    timestamp_sn = timestamp_ms / 1000
                    kalkis_saati_str = datetime.fromtimestamp(timestamp_sn).strftime("%H:%M")
                    tren_adi = tren.get("trainName", f"Tren {toplam_tren_sayaci}")
                    
                    # Saat filtresi: Seçilen saatler varsa ve bu saat listede yoksa atla
                    if selected_times and kalkis_saati_str not in selected_times:
                        continue
                    
                    tren_mesaj_taslagi += f"\n<b>{tren_adi} (Kalkış: {kalkis_saati_str})</b>:\n"
                    
                    vagon_bilgisi_sozlugu = tren["availableFareInfo"][0]
                    vagon_siniflari_listesi = vagon_bilgisi_sozlugu["cabinClasses"]
                    
                    if not vagon_siniflari_listesi:
                        continue

                    for vagon in vagon_siniflari_listesi:
                        sinif_adi = vagon["cabinClass"]["name"]
                        uygun_koltuk = vagon["availabilityCount"]
                        
                        # İstenmeyen vagon tipleri
                        unwanted_types = ["TEKERLEKLİ SANDALYE", "YATAKLI", "LOCA"]
                        
                        # Business filtresi
                        if not include_business and "BUS" in sinif_adi.upper():
                            continue
                        
                        if sinif_adi.upper() in unwanted_types:
                            continue
                        
                        # Minimum koltuk filtresi
                        if uygun_koltuk >= min_seats:
                            bulunan_koltuk = True
                            vagon_bulundu_bu_trende = True
                            minimum_fiyat = vagon["minPrice"]
                            tren_mesaj_taslagi += f"   ✅ <b>{sinif_adi}: {uygun_koltuk} adet</b> (min {minimum_fiyat} TRY)\n"

                    if vagon_bulundu_bu_trende:
                         result_message += tren_mesaj_taslagi
                         
                except (KeyError, IndexError, TypeError) as e:
                    print(f"Parsing error: {e}")

        if not bulunan_koltuk:
            return (False, f"ℹ️ {route_str} yönüne sefer bulundu, ancak <b>kriterlere uygun yer bulunamadı</b>.")
        else:
            return (True, result_message)

    except Exception as e:
        return (False, f"❌ HATA: {e}")

def run_one_time_check(chat_id: str, from_id: int, to_id: int, target_date: datetime):
    from_station = get_station_by_id(from_id)
    to_station = get_station_by_id(to_id)
    
    print(f"Tek seferlik kontrol: {chat_id} | {from_station['name']} -> {to_station['name']}")
    
    found, message = check_api_and_parse(from_id, to_id, target_date)
    send_telegram_message(message, chat_id)
    print(f"Tek seferlik kontrol tamamlandı ({chat_id}).")

def monitoring_loop(chat_id: str, stop_event: threading.Event, from_id: int, to_id: int, 
                     target_date: datetime, interval_seconds: int,
                     selected_times: list = None, include_business: bool = True, min_seats: int = 1):
    """
    Sürekli izleme döngüsü.
    
    Args:
        selected_times: Sadece bu saatlerdeki trenleri izle (None = hepsi)
        include_business: Business sınıfını dahil et
        min_seats: Minimum koltuk sayısı filtresi
    """
    from_station = get_station_by_id(from_id)
    to_station = get_station_by_id(to_id)
    
    # Filtre özeti oluştur
    filter_info = []
    if selected_times:
        times_str = ", ".join(selected_times)
        filter_info.append(f"⏰ Saatler: {times_str}")
    else:
        filter_info.append("⏰ Saatler: Tümü")
    
    filter_info.append(f"💼 Business: {'Dahil' if include_business else 'Hariç'}")
    filter_info.append(f"👥 Min. Koltuk: {min_seats}")
    
    filter_summary = "\n".join(filter_info)
    
    print(f"API İzleme başladı: {chat_id} | {from_station['name']} -> {to_station['name']}")
    send_telegram_message(
        f"🚂 *Takip başladı!*\n\n"
        f"*{from_station['name']} ➡ {to_station['name']}*\n"
        f"📅 {target_date.strftime('%d %B %Y')}\n\n"
        f"*Filtreler:*\n{filter_summary}\n\n"
        f"🔄 {interval_seconds} saniyede bir kontrol edilecek.",
        chat_id
    )
    
    previous_state = {}
    first_check = True
    
    while not stop_event.is_set():
        print(f"API Kontrol ediliyor ({chat_id})...")
        
        found, message = check_api_and_parse(from_id, to_id, target_date, 
                                              selected_times, include_business, min_seats)
        
        current_state = {}
        
        if found:
            lines = message.split('\n')
            current_train = None
            current_train_total = 0
            
            for line in lines:
                if line.strip().startswith('<b>') and 'Kalkış:' in line:
                    if current_train:
                        current_state[current_train] = current_train_total
                    
                    train_info = line.split('(Kalkış:')[0].strip()
                    train_info = train_info.replace('<b>', '').replace('</b>', '')
                    current_train = train_info
                    current_train_total = 0
                
                elif '✅' in line and 'adet' in line:
                    try:
                        seat_count = int(line.split(':')[1].split('adet')[0].strip())
                        current_train_total += seat_count
                    except:
                        pass
            
            if current_train:
                current_state[current_train] = current_train_total
        
        if first_check:
            if found:
                print(f"İLK KONTROL - BOŞ YER BULUNDU! ({chat_id})")
                send_telegram_message("🎫 İLK KONTROL - BİLET DURUMU:\n\n" + message, chat_id)
                previous_state = current_state.copy()
            else:
                print(f"İLK KONTROL - BOŞ YER YOK ({chat_id})")
                send_telegram_message("ℹ️ İlk kontrol tamamlandı. Şu anda kriterlere uygun yer bulunmuyor. Yer açıldığında bildirim alacaksınız.", chat_id)
            first_check = False
        
        else:
            if found:
                changes_detected = False
                change_message = "🚨 YENİ YER AÇILDI! 🚨\n\n"
                
                for train_name, current_seats in current_state.items():
                    previous_seats = previous_state.get(train_name, 0)
                    
                    if current_seats > previous_seats:
                        changes_detected = True
                        if previous_seats == 0:
                            change_message += f"🆕 <b>{train_name}</b>: YENİ SEFER - {current_seats} koltuk bulundu!\n"
                        else:
                            change_message += f"📈 <b>{train_name}</b>: {previous_seats} → {current_seats} koltuk (+{current_seats - previous_seats})\n"
                
                if changes_detected:
                    print(f"DEĞİŞİKLİK TESPİT EDİLDİ! ({chat_id})")
                    change_message += "\n" + message
                    send_telegram_message(change_message, chat_id)
                    previous_state = current_state.copy()
                else:
                    print(f"Değişiklik yok, mesaj atılmadı ({chat_id})")
            
            elif previous_state:
                print(f"TÜM YERLER DOLDU! ({chat_id})")
                send_telegram_message("❌ Daha önce uygun olan yerler doldu. Yeni yer açılmasını bekliyorum...", chat_id)
                previous_state = {}
        
        print(f"{interval_seconds} saniye bekleniyor...")
        if stop_event.wait(interval_seconds):
            break
            
    print(f"API İzleme durdu ({chat_id}).")
    if chat_id in monitor_jobs:
        del monitor_jobs[chat_id]
        print(f"İzleme işi listeden kaldırıldı ({chat_id}).")

def create_date_keyboard(action: str, from_station_id: int, to_station_id: int) -> InlineKeyboardMarkup:
    keyboard = []
    today = datetime.today()
    
    row = []
    for i in range(0, 13):
        day = today + timedelta(days=i)
        date_str_iso = day.strftime("%Y-%m-%d")
        
        callback_data = f"date_{action}_{from_station_id}_{to_station_id}_{date_str_iso}"
        
        if i == 0:
            day_name = "Bugün"
        elif i == 1:
            day_name = "Yarın"
        else:
            day_name = day.strftime("%A")
        
        button_text = f"{day_name.capitalize()} ({day.strftime('%d %b').capitalize()})"
        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row: 
        keyboard.append(row)
        
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: CallbackContext):
    message = """
👋 Merhaba! Ben TCDD API Bilet Takip Botuyum.

*KOMUTLAR:*
• `/check` - Tek seferlik bilet kontrolü
• `/monitor` - Sürekli bilet takibi
• `/stop` - Aktif izlemeyi durdurur

İstasyonlar TCDD'den dinamik olarak yüklenir.
    """
    await update.message.reply_text(message, parse_mode='Markdown')

async def check_command(update: Update, context: CallbackContext):
    chat_id = str(update.message.chat_id)
    cleanup_ids = [update.message.message_id]
    
    if not STATIONS_DATA:
        loading_msg = await update.message.reply_text("⏳ İstasyonlar yükleniyor, lütfen bekleyin...")
        cleanup_ids.append(loading_msg.message_id)
        if not load_stations():
            await update.message.reply_text("❌ İstasyonlar yüklenemedi. Lütfen daha sonra tekrar deneyin.")
            return
    
    # Kullanıcı durumunu kaydet
    user_states[chat_id] = {
        "state": "waiting_from",
        "action": "check",
        "from_station_id": None,
        "cleanup_ids": cleanup_ids
    }
    
    msg = await update.message.reply_text(
        "🔍 *Kalkış İstasyonu Araması*\n\n"
        "Lütfen kalkış istasyonu adını yazın (en az 3 karakter).\n"
        "Örnek: `Ankara`, `İstanbul`, `İzmir`",
        parse_mode='Markdown'
    )
    user_states[chat_id]["cleanup_ids"].append(msg.message_id)

async def monitor_command(update: Update, context: CallbackContext):
    chat_id = str(update.message.chat_id)
    cleanup_ids = [update.message.message_id]
    
    if chat_id in monitor_jobs:
        await delete_messages(context, chat_id, cleanup_ids)
        await update.message.reply_text("Zaten aktif bir izlemeniz var. Durdurmak için /stop yazın.")
        return
    
    if not STATIONS_DATA:
        loading_msg = await update.message.reply_text("⏳ İstasyonlar yükleniyor, lütfen bekleyin...")
        cleanup_ids.append(loading_msg.message_id)
        if not load_stations():
            await update.message.reply_text("❌ İstasyonlar yüklenemedi. Lütfen daha sonra tekrar deneyin.")
            return
    
    # Kullanıcı durumunu kaydet
    user_states[chat_id] = {
        "state": "waiting_from",
        "action": "monitor",
        "from_station_id": None,
        "cleanup_ids": cleanup_ids
    }
    
    msg = await update.message.reply_text(
        "🔍 *Kalkış İstasyonu Araması*\n\n"
        "Lütfen kalkış istasyonu adını yazın (en az 3 karakter).\n"
        "Örnek: `Ankara`, `İstanbul`, `İzmir`",
        parse_mode='Markdown'
    )
    user_states[chat_id]["cleanup_ids"].append(msg.message_id)

async def stop_command(update: Update, context: CallbackContext):
    chat_id = str(update.message.chat_id)
    
    if chat_id in monitor_jobs:
        monitor_thread, stop_event = monitor_jobs.pop(chat_id)
        print(f"Durdurma sinyali gönderiliyor: {chat_id}")
        stop_event.set()
        await update.message.reply_text("İzleme durduruluyor... 🛑")
    else:
        await update.message.reply_text("Aktif bir izlemeniz bulunmuyor.")

async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    chat_id = str(query.message.chat_id)
    
    try:
        if query.data == "cancel_search":
            if chat_id in user_states:
                cleanup_ids = user_states[chat_id].get("cleanup_ids", [])
                cleanup_ids.append(query.message.message_id)
                await delete_messages(context, chat_id, cleanup_ids)
                del user_states[chat_id]
            else:
                await query.edit_message_text("❌ İşlem iptal edildi.")
            return
        
        parts = query.data.split('_')
        prefix = parts[0]

        if prefix == 'from':
            action = parts[1]
            from_station_id = int(parts[2])
            from_station = get_station_by_id(from_station_id)
            
            cleanup_ids = user_states[chat_id].get("cleanup_ids", []) if chat_id in user_states else []
            user_states[chat_id] = {
                "state": "waiting_to",
                "action": action,
                "from_station_id": from_station_id,
                "cleanup_ids": cleanup_ids
            }
            
            await query.edit_message_text(
                text=f"✅ Kalkış: *{from_station['name']}*\n\n"
                     f"🔍 *Varış İstasyonu Araması*\n\n"
                     f"Lütfen varış istasyonu adını yazın (en az 3 karakter).",
                parse_mode='Markdown'
            )
        
        elif prefix == 'to':
            action = parts[1]
            from_station_id = int(parts[2])
            to_station_id = int(parts[3])
            
            cleanup_ids = user_states[chat_id].get("cleanup_ids", []) if chat_id in user_states else []
            
            user_states[chat_id] = {
                "state": "waiting_date",
                "action": action,
                "from_station_id": from_station_id,
                "to_station_id": to_station_id,
                "cleanup_ids": cleanup_ids
            }
            
            from_station = get_station_by_id(from_station_id)
            to_station = get_station_by_id(to_station_id)
            
            keyboard = create_date_keyboard(action=action, from_station_id=from_station_id, to_station_id=to_station_id)
            await query.edit_message_text(
                text=f"Kalkış: *{from_station['name']}*\nVarış: *{to_station['name']}*\n\nLütfen bir *tarih* seçin:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif prefix == 'date':
            action = parts[1]
            from_station_id = int(parts[2])
            to_station_id = int(parts[3])
            date_iso_str = parts[4]
            target_date = datetime.strptime(date_iso_str, "%Y-%m-%d")
            
            from_station = get_station_by_id(from_station_id)
            to_station = get_station_by_id(to_station_id)
            
            date_tr_str = target_date.strftime("%d %B %Y")
            
            cleanup_ids = user_states[chat_id].get("cleanup_ids", []) if chat_id in user_states else []

            if action == "check":
                cleanup_ids.append(query.message.message_id)
                await delete_messages(context, chat_id, cleanup_ids)
                
                print(f"Check başlatıldı: {from_station['name']} -> {to_station['name']}")
                threading.Thread(
                    target=run_one_time_check,
                    args=(chat_id, from_station_id, to_station_id, target_date)
                ).start()
                
                if chat_id in user_states:
                    del user_states[chat_id]
                return
            
            elif action == "monitor":
                if chat_id in monitor_jobs:
                    await query.message.reply_text("Zaten aktif bir izlemeniz var. /stop")
                    return
                
                await query.edit_message_text(
                    text=f"🚆 *{from_station['name']}* ➡ *{to_station['name']}*\n🗓 *{date_tr_str}*\n\n⏳ Sefer saatleri alınıyor...", 
                    parse_mode='Markdown'
                )
                
                # Sefer saatlerini al
                available_times = get_available_train_times(from_station_id, to_station_id, target_date)
                
                if not available_times:
                    cleanup_ids = user_states[chat_id].get("cleanup_ids", []) if chat_id in user_states else []
                    cleanup_ids.append(query.message.message_id)
                    await delete_messages(context, chat_id, cleanup_ids)
                    
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ *{from_station['name']}* ➡ *{to_station['name']}*\n🗓 *{date_tr_str}*\n\nBu tarihte sefer bulunamadı.", 
                        parse_mode='Markdown'
                    )
                    
                    if chat_id in user_states:
                        del user_states[chat_id]
                    return
                
                user_states[chat_id] = {
                    "state": "selecting_times",
                    "action": "monitor",
                    "from_station_id": from_station_id,
                    "to_station_id": to_station_id,
                    "target_date": target_date,
                    "available_times": available_times,
                    "selected_times": [t["time"] for t in available_times],  # Başta hepsi seçili
                    "include_business": False,
                    "min_seats": 1,
                    "cleanup_ids": cleanup_ids
                }
                
                # Saatleri göster
                # Tren tipini belirle
                type_display = ""
                if t.get("train_type") == "YHT":
                    type_display = " (YHT)"
                elif t.get("train_type") == "AH":
                    type_display = " (Anahat)"
                
                times_info = "\n".join([f"• {t['time']}{type_display} - {t['train_name']}" for t in available_times[:10]])
                keyboard = create_time_selection_keyboard(
                    available_times, 
                    user_states[chat_id]["selected_times"],
                    "mtime"
                )
                await query.edit_message_text(
                    text=f"🚆 *{from_station['name']}* ➡ *{to_station['name']}*\n🗓 *{date_tr_str}*\n\n"
                         f"*Mevcut Seferler:*\n{times_info}\n\n"
                         f"⏰ *İzlemek istediğiniz saatleri seçin:*\n(Seçili olanlar ✅ ile gösterilir)",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        
        elif prefix == 'mtime':
            if chat_id not in user_states or user_states[chat_id].get("state") != "selecting_times":
                try: await query.message.delete()
                except: pass
                await context.bot.send_message(chat_id=chat_id, text="❌ Oturum süresi doldu. Lütfen /monitor ile tekrar başlayın.")
                return
            
            state = user_states[chat_id]
            sub_action = parts[1]
            
            if sub_action == "toggle":
                time_str = parts[2]
                if time_str in state["selected_times"]:
                    state["selected_times"].remove(time_str)
                else:
                    state["selected_times"].append(time_str)
                
                # Klavyeyi güncelle
                keyboard = create_time_selection_keyboard(
                    state["available_times"],
                    state["selected_times"],
                    "mtime"
                )
                await query.edit_message_reply_markup(reply_markup=keyboard)
            
            elif sub_action == "all":
                # Tümünü seç/temizle
                if len(state["selected_times"]) < len(state["available_times"]):
                    state["selected_times"] = [t["time"] for t in state["available_times"]]
                else:
                    state["selected_times"] = []
                
                keyboard = create_time_selection_keyboard(
                    state["available_times"],
                    state["selected_times"],
                    "mtime"
                )
                await query.edit_message_reply_markup(reply_markup=keyboard)
            
            elif sub_action == "done":
                if not state["selected_times"]:
                    await query.answer("⚠️ En az bir saat seçmelisiniz!", show_alert=True)
                    return
                
                # Business seçimine geç
                state["state"] = "selecting_business"
                keyboard = create_business_keyboard("mbiz")
                
                from_station = get_station_by_id(state["from_station_id"])
                to_station = get_station_by_id(state["to_station_id"])
                date_tr_str = state["target_date"].strftime("%d %B %Y")
                
                # Saatleri tren tipleriyle birlikte göster
                selected_times_with_types = []
                for time_str in sorted(state["selected_times"]):
                    # available_times'dan tren tipini bul
                    train_info = next((t for t in state["available_times"] if t["time"] == time_str), None)
                    type_display = ""
                    if train_info and train_info.get("train_type") == "YHT":
                        type_display = " (YHT)"
                    elif train_info and train_info.get("train_type") == "AH":
                        type_display = " (Anahat)"
                    selected_times_with_types.append(f"{time_str}{type_display}")
                
                times_str = ", ".join(selected_times_with_types)
                
                await query.edit_message_text(
                    text=f"🚆 *{from_station['name']}* ➡ *{to_station['name']}*\n🗓 *{date_tr_str}*\n"
                         f"⏰ Saatler: {times_str}\n\n"
                         f"💼 *Business sınıfını dahil etmek ister misiniz?*",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        
        elif prefix == 'mbiz':
            if chat_id not in user_states or user_states[chat_id].get("state") != "selecting_business":
                try: await query.message.delete()
                except: pass
                await context.bot.send_message(chat_id=chat_id, text="❌ Oturum süresi doldu. Lütfen /monitor ile tekrar başlayın.")
                return
            
            state = user_states[chat_id]
            include_business = parts[1] == "yes"
            state["include_business"] = include_business
            
            # Kişi sayısı seçimine geç
            state["state"] = "selecting_count"
            keyboard = create_passenger_count_keyboard("mcount")
            
            from_station = get_station_by_id(state["from_station_id"])
            to_station = get_station_by_id(state["to_station_id"])
            date_tr_str = state["target_date"].strftime("%d %B %Y")
            
            # Saatleri tren tipleriyle birlikte göster
            selected_times_with_types = []
            for time_str in sorted(state["selected_times"]):
                # available_times'dan tren tipini bul
                train_info = next((t for t in state["available_times"] if t["time"] == time_str), None)
                type_display = ""
                if train_info and train_info.get("train_type") == "YHT":
                    type_display = " (YHT)"
                elif train_info and train_info.get("train_type") == "AH":
                    type_display = " (Anahat)"
                selected_times_with_types.append(f"{time_str}{type_display}")
            
            times_str = ", ".join(selected_times_with_types)
            biz_str = "Dahil" if include_business else "Hariç"
            
            await query.edit_message_text(
                text=f"🚆 *{from_station['name']}* ➡ *{to_station['name']}*\n🗓 *{date_tr_str}*\n"
                     f"⏰ Saatler: {times_str}\n💼 Business: {biz_str}\n\n"
                     f"👥 *Kaç kişilik yer arıyorsunuz?*\n(En az bu kadar boş yer olunca bildirim alacaksınız)",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        
        elif prefix == 'mcount':
            if chat_id not in user_states or user_states[chat_id].get("state") != "selecting_count":
                try: await query.message.delete()
                except: pass
                await context.bot.send_message(chat_id=chat_id, text="❌ Oturum süresi doldu. Lütfen /monitor ile tekrar başlayın.")
                return
            
            state = user_states[chat_id]
            min_seats = int(parts[1])
            state["min_seats"] = min_seats
            
            # İzleme sıklığı seçimine geç
            state["state"] = "selecting_interval"
            keyboard = create_interval_selection_keyboard("minterval")
            
            from_station = get_station_by_id(state["from_station_id"])
            to_station = get_station_by_id(state["to_station_id"])
            date_tr_str = state["target_date"].strftime("%d %B %Y")
            
            # Saatleri tren tipleriyle birlikte göster
            selected_times_with_types = []
            for time_str in sorted(state["selected_times"]):
                # available_times'dan tren tipini bul
                train_info = next((t for t in state["available_times"] if t["time"] == time_str), None)
                type_display = ""
                if train_info and train_info.get("train_type") == "YHT":
                    type_display = " (YHT)"
                elif train_info and train_info.get("train_type") == "AH":
                    type_display = " (Anahat)"
                selected_times_with_types.append(f"{time_str}{type_display}")
            
            times_str = ", ".join(selected_times_with_types)
            biz_str = "Dahil" if state["include_business"] else "Hariç"
            
            await query.edit_message_text(
                text=f"🚆 *{from_station['name']}* ➡ *{to_station['name']}*\n🗓 *{date_tr_str}*\n"
                     f"⏰ Saatler: {times_str}\n💼 Business: {biz_str}\n👥 Min. Yer: {min_seats}\n\n"
                     f"🔄 *Hangi sıklıkla kontrol edilsin?*",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

        elif prefix == 'minterval':
            if chat_id not in user_states or user_states[chat_id].get("state") != "selecting_interval":
                try: await query.message.delete()
                except: pass
                await context.bot.send_message(chat_id=chat_id, text="❌ Oturum süresi doldu. Lütfen /monitor ile tekrar başlayın.")
                return
            
            state = user_states[chat_id]
            check_interval = int(parts[1])
            
            # İzlemeyi başlat
            from_station = get_station_by_id(state["from_station_id"])
            to_station = get_station_by_id(state["to_station_id"])
            date_tr_str = state["target_date"].strftime("%d %B %Y")
            
            # Önceki tüm ara mesajları temizle
            cleanup_ids = state.get("cleanup_ids", [])
            # Şu anki butonlu mesajın ID'sini de ekle
            cleanup_ids.append(query.message.message_id)
            await delete_messages(context, chat_id, cleanup_ids)
            
            # Monitor thread'i başlat
            stop_event = threading.Event()
            monitor_thread = threading.Thread(
                target=monitoring_loop,
                args=(chat_id, stop_event, state["from_station_id"], state["to_station_id"], 
                      state["target_date"], check_interval, 
                      state["selected_times"], state["include_business"], state["min_seats"])
            )
            
            monitor_jobs[chat_id] = (monitor_thread, stop_event)
            monitor_thread.start()
            
            # Kullanıcı durumunu temizle
            del user_states[chat_id]

    except Exception as e:
        print(f"Callback hatası: {e}")
        import traceback
        traceback.print_exc()
        
        # Hata durumunda da temizlik dene
        if chat_id in user_states:
            cleanup_ids = user_states[chat_id].get("cleanup_ids", [])
            cleanup_ids.append(query.message.message_id)
            await delete_messages(context, chat_id, cleanup_ids)
            del user_states[chat_id]
        
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Bir hata oluştu ve işlem iptal edildi: {e}")

async def text_message_handler(update: Update, context: CallbackContext):
    chat_id = str(update.message.chat_id)
    
    if chat_id not in user_states:
        return
    
    user_state = user_states[chat_id]
    user_state["cleanup_ids"].append(update.message.message_id)
    
    try:
        search_query = update.message.text.strip()
        
        # Minimum 3 karakter kontrolü
        if len(search_query) < 3:
            msg = await update.message.reply_text(
                "⚠️ Lütfen en az 3 karakter girin.\n"
                "Örnek: `Ank`, `İst`, `İzm`",
                parse_mode='Markdown'
            )
            user_state["cleanup_ids"].append(msg.message_id)
            return
        
        action = user_state["action"]
        state = user_state["state"]
        
        if state == "waiting_from":
            results = search_stations(search_query)
            
            if not results:
                msg = await update.message.reply_text(
                    f"❌ *'{search_query}'* için istasyon bulunamadı.\n\n"
                    "Lütfen farklı bir arama terimi deneyin.",
                    parse_mode='Markdown'
                )
                user_state["cleanup_ids"].append(msg.message_id)
                return
            
            keyboard = create_search_result_keyboard(results, action)
            msg = await update.message.reply_text(
                f"🔍 *'{search_query}'* için {len(results)} sonuç bulundu:\n\n"
                "Lütfen kalkış istasyonunu seçin:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            user_state["cleanup_ids"].append(msg.message_id)
        
        elif state == "waiting_to":
            from_station_id = user_state["from_station_id"]
            from_station = get_station_by_id(from_station_id)
            
            results = search_stations(search_query, from_station_id)
            
            if not results:
                msg = await update.message.reply_text(
                    f"❌ *'{search_query}'* için varış istasyonu bulunamadı.\n\n"
                    f"*{from_station['name']}* istasyonundan gidilebilecek farklı bir istasyon arayın.",
                    parse_mode='Markdown'
                )
                user_state["cleanup_ids"].append(msg.message_id)
                return
            
            keyboard = create_search_result_keyboard(results, action, from_station_id)
            msg = await update.message.reply_text(
                f"✅ Kalkış: *{from_station['name']}*\n\n"
                f"🔍 *'{search_query}'* için {len(results)} sonuç bulundu:\n\n"
                "Lütfen varış istasyonunu seçin:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            user_state["cleanup_ids"].append(msg.message_id)
            
    except Exception as e:
        print(f"Metin mesajı işleme hatası: {e}")
        import traceback
        traceback.print_exc()
        if chat_id in user_states:
            cleanup_ids = user_states[chat_id].get("cleanup_ids", [])
            await delete_messages(context, chat_id, cleanup_ids)
            del user_states[chat_id]
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Bir hata oluştu ve işlem iptal edildi: {e}")

def main():
    print("🚂 TCDD Bilet Takip Botu başlatılıyor...")
    
    if not load_stations():
        print("⚠️ İstasyonlar yüklenemedi, bot yine de başlatılıyor...")
    
    builder = Application.builder().token(TELEGRAM_API_TOKEN)
    app = builder.build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("monitor", monitor_command))
    app.add_handler(CommandHandler("stop", stop_command))
    
    app.add_handler(CallbackQueryHandler(button_callback, pattern='^(from_|to_|date_|mtime_|mbiz_|mcount_|minterval_|cancel_search)'))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    print("✅ Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
