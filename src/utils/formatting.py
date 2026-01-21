"""
Mesaj formatlama yardımcıları.
"""
from datetime import date, datetime
from typing import Optional

from ..models import Station, SearchResult, TrainResult, MonitorConfig


def escape_html(text: str) -> str:
    """HTML karakterlerini escape eder"""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;'))


def format_date_turkish(d: date) -> str:
    """Tarihi Türkçe olarak formatlar"""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d %B %Y")


def format_route(from_station: Station, to_station: Station) -> str:
    """Güzergahı formatlar"""
    return f"{from_station.name} ➡ {to_station.name}"


def format_route_with_date(
    from_station: Station, 
    to_station: Station, 
    target_date: date
) -> str:
    """Güzergah ve tarihi formatlar"""
    route = format_route(from_station, to_station)
    date_str = format_date_turkish(target_date)
    return f"<b>{route}</b> | <b>{date_str}</b>"


def format_train_info(train_result: TrainResult) -> str:
    """Tren bilgisini formatlar"""
    train = train_result.train
    lines = [f"\n<b>{train.name} (Kalkış: {train.get_departure_time_str()})</b>:"]
    
    for cabin in train_result.available_cabins:
        lines.append(
            f"   ✅ <b>{cabin.name}: {cabin.available_seats} adet</b> "
            f"(min {cabin.min_price:.0f} TRY)"
        )
    
    return "\n".join(lines)


def format_search_result(result: SearchResult, from_station: Station, to_station: Station, target_date: date) -> str:
    """Arama sonucunu Telegram mesajı olarak formatlar"""
    header = format_route_with_date(from_station, to_station, target_date)
    
    if not result.success:
        return f"❌ {header}\n\n{result.error or result.message}"
    
    if not result.has_availability:
        return f"ℹ️ {header}\n\n<b>Kriterlere uygun yer bulunamadı.</b>"
    
    lines = [f"✅ {header}\n\nBulunan seferler:"]
    
    for train_result in result.trains:
        lines.append(format_train_info(train_result))
    
    return "\n".join(lines)


def format_monitor_start(config: MonitorConfig, from_station: Station, to_station: Station) -> str:
    """İzleme başlangıç mesajını formatlar"""
    filter_lines = []
    
    if config.selected_times:
        times_str = ", ".join(sorted(config.selected_times))
        filter_lines.append(f"⏰ Saatler: {times_str}")
    else:
        filter_lines.append("⏰ Saatler: Tümü")
    
    filter_lines.append(f"💼 Business: {'Dahil' if config.include_business else 'Hariç'}")
    filter_lines.append(f"👥 Min. Koltuk: {config.min_seats}")
    
    filter_summary = "\n".join(filter_lines)
    date_str = format_date_turkish(config.target_date)
    
    return (
        f"🚂 *Takip başladı!*\n\n"
        f"*{from_station.name} ➡ {to_station.name}*\n"
        f"📅 {date_str}\n\n"
        f"*Filtreler:*\n{filter_summary}\n\n"
        f"🔄 {config.check_interval} saniyede bir kontrol edilecek."
    )


def format_change_notification(result: SearchResult, changes: dict) -> str:
    """Değişiklik bildirimini formatlar"""
    change_type = changes.get("type", "")
    
    if change_type == "first_check":
        if changes.get("has_availability"):
            return "🎫 İLK KONTROL - BİLET DURUMU:\n\n"
        else:
            return "ℹ️ İlk kontrol tamamlandı. Şu anda kriterlere uygun yer bulunmuyor. Yer açıldığında bildirim alacaksınız."
    
    elif change_type == "new_availability":
        lines = ["🚨 YENİ YER AÇILDI! 🚨\n"]
        
        change_data = changes.get("changes", {})
        
        for new_train in change_data.get("new_trains", []):
            lines.append(f"🆕 <b>{new_train['name']}</b>: YENİ SEFER - {new_train['seats']} koltuk bulundu!")
        
        for increased in change_data.get("increased", []):
            lines.append(f"📈 <b>{increased['name']}</b>: {increased['from']} → {increased['to']} koltuk")
        
        return "\n".join(lines)
    
    elif change_type == "all_gone":
        return "❌ Daha önce uygun olan yerler doldu. Yeni yer açılmasını bekliyorum..."
    
    return ""
