"""
Telegram InlineKeyboard oluşturucular.
"""
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ...models import Station, TrainTime


def create_search_result_keyboard(
    stations: list[Station], 
    action: str, 
    from_station_id: int = None
) -> InlineKeyboardMarkup:
    """Arama sonuçlarından buton klavyesi oluşturur"""
    keyboard = []
    row = []
    
    if from_station_id:
        prefix = f"to_{action}_{from_station_id}"
    else:
        prefix = f"from_{action}"
    
    for station in stations:
        station_name = station.name[:25]  # Uzun isimleri kısalt
        callback_data = f"{prefix}_{station.id}"
        
        row.append(InlineKeyboardButton(station_name, callback_data=callback_data))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="cancel_search")])
    
    return InlineKeyboardMarkup(keyboard)


def create_date_keyboard(
    action: str, 
    from_station_id: int, 
    to_station_id: int,
    days: int = 14
) -> InlineKeyboardMarkup:
    """Tarih seçim klavyesi oluşturur"""
    keyboard = []
    today = datetime.today()
    
    row = []
    for i in range(days):
        day = today + timedelta(days=i)
        day_str = day.strftime("%d %b")
        callback_data = f"date_{action}_{from_station_id}_{to_station_id}_{day.strftime('%Y-%m-%d')}"
        
        row.append(InlineKeyboardButton(day_str, callback_data=callback_data))
        
        if len(row) == 4:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="cancel_search")])
    
    return InlineKeyboardMarkup(keyboard)


def create_time_selection_keyboard(
    available_times: list[TrainTime], 
    selected_times: list[str]
) -> InlineKeyboardMarkup:
    """Saat seçim klavyesi oluşturur"""
    keyboard = []
    row = []
    
    for train_time in available_times:
        time_str = train_time.time
        is_selected = time_str in selected_times
        
        button_text = f"✅ {time_str}" if is_selected else time_str
        callback_data = f"mtime_toggle_{time_str}"
        
        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    select_all_text = "📋 Tümünü Seç" if len(selected_times) < len(available_times) else "🔄 Seçimi Temizle"
    keyboard.append([
        InlineKeyboardButton(select_all_text, callback_data="mtime_all"),
        InlineKeyboardButton("➡️ Devam", callback_data="mtime_done")
    ])
    
    keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="cancel_search")])
    
    return InlineKeyboardMarkup(keyboard)


def create_business_keyboard() -> InlineKeyboardMarkup:
    """Business class dahil/hariç seçim klavyesi"""
    keyboard = [
        [
            InlineKeyboardButton("🪑 Sadece Ekonomi", callback_data="mbiz_no"),
            InlineKeyboardButton("💼 Business Dahil", callback_data="mbiz_yes")
        ],
        [InlineKeyboardButton("❌ İptal", callback_data="cancel_search")]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_passenger_count_keyboard() -> InlineKeyboardMarkup:
    """Kişi sayısı seçim klavyesi (1-6)"""
    keyboard = [
        [
            InlineKeyboardButton("1 Kişi", callback_data="mcount_1"),
            InlineKeyboardButton("2 Kişi", callback_data="mcount_2"),
            InlineKeyboardButton("3 Kişi", callback_data="mcount_3")
        ],
        [
            InlineKeyboardButton("4 Kişi", callback_data="mcount_4"),
            InlineKeyboardButton("5 Kişi", callback_data="mcount_5"),
            InlineKeyboardButton("6 Kişi", callback_data="mcount_6")
        ],
        [InlineKeyboardButton("❌ İptal", callback_data="cancel_search")]
    ]
    return InlineKeyboardMarkup(keyboard)
