"""
Telegram komut ve callback handler'ları.
"""
import functools
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from .session import SessionManager, UserSession
from .keyboards import (
    create_search_result_keyboard,
    create_date_keyboard,
    create_time_selection_keyboard,
    create_business_keyboard,
    create_passenger_count_keyboard
)
from ...models import MonitorConfig
from ...services import StationService, TicketService, MonitorService, AuthService
from ...utils import format_search_result, format_monitor_start, format_change_notification, format_date_turkish


def auth_required(func):
    """Yetkilendirme kontrol decorator'ı"""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: CallbackContext, *args, **kwargs):
        # Callback query veya message üzerinden chat_id al
        if update.callback_query:
            chat_id = str(update.callback_query.message.chat_id)
            message = update.callback_query.message
        else:
            chat_id = str(update.message.chat_id)
            message = update.message

        # Yetki kontrolü
        if not self.auth_service.is_authenticated(chat_id):
            await message.reply_text(
                "🔒 Bu botu kullanmak için şifre girmelisiniz.\n"
                "Lütfen şifreyi yazın:\n\n"
                "(Sadece şifreyi gönderin)"
            )
            # Yetkisiz durumda akışı durdur
            return

        return await func(self, update, context, *args, **kwargs)
    return wrapper


class TelegramHandlers:
    """Telegram bot handler'ları"""
    
    def __init__(
        self,
        station_service: StationService,
        ticket_service: TicketService,
        monitor_service: MonitorService,
        auth_service: AuthService,
        session_manager: SessionManager
    ):
        self.station_service = station_service
        self.ticket_service = ticket_service
        self.monitor_service = monitor_service
        self.auth_service = auth_service
        self.sessions = session_manager
        self._send_message: callable = None
    
    def set_message_sender(self, sender: callable):
        """Mesaj gönderici fonksiyonu ayarlar"""
        self._send_message = sender
    
    # ================== COMMAND HANDLERS ==================
    
    @auth_required
    async def start_command(self, update: Update, context: CallbackContext):
        """"/start komutu"""
        await update.message.reply_text(
            "🚂 *TCDD Bilet Takip Botu*\n\n"
            "Komutlar:\n"
            "/check - Anlık bilet kontrolü\n"
            "/monitor - Yeni takip başlat\n"
            "/status - Aktif takipleri yönet\n"
            "/stop - Tüm takipleri durdur\n\n"
            "Bilet boşaldığında bildirim alırsınız!",
            parse_mode='Markdown'
        )
    
    @auth_required
    async def check_command(self, update: Update, context: CallbackContext):
        """/check komutu"""
        chat_id = str(update.message.chat_id)
        
        if not self.station_service.is_loaded:
            await update.message.reply_text("⏳ İstasyonlar yükleniyor, lütfen bekleyin...")
            if not self.station_service.load_stations():
                await update.message.reply_text("❌ İstasyonlar yüklenemedi. Lütfen daha sonra tekrar deneyin.")
                return
        
        session = self.sessions.get_or_create(chat_id)
        session.clear()
        session.state = "waiting_from"
        session.action = "check"
        
        await update.message.reply_text(
            "🔍 *Kalkış İstasyonu Araması*\n\n"
            "Lütfen kalkış istasyonu adını yazın (en az 3 karakter).\n"
            "Örnek: `Ankara`, `İstanbul`, `İzmir`",
            parse_mode='Markdown'
        )
    
    @auth_required
    async def monitor_command(self, update: Update, context: CallbackContext):
        """/monitor komutu (Yeni monitor başlatır)"""
        chat_id = str(update.message.chat_id)
        
        if not self.station_service.is_loaded:
            await update.message.reply_text("⏳ İstasyonlar yükleniyor, lütfen bekleyin...")
            if not self.station_service.load_stations():
                await update.message.reply_text("❌ İstasyonlar yüklenemedi. Lütfen daha sonra tekrar deneyin.")
                return
        
        session = self.sessions.get_or_create(chat_id)
        session.clear()
        session.state = "waiting_from"
        session.action = "monitor"
        
        await update.message.reply_text(
            "🆕 *Yeni Takip Başlat*\n\n"
            "🔍 *Kalkış İstasyonu Araması*\n"
            "Lütfen kalkış istasyonu adını yazın (en az 3 karakter).",
            parse_mode='Markdown'
        )
    
    @auth_required
    async def status_command(self, update: Update, context: CallbackContext):
        """/status komutu - Aktif takipleri listeler"""
        chat_id = str(update.message.chat_id)
        active_monitors = self.monitor_service.get_user_monitors(chat_id)
        
        if not active_monitors:
            await update.message.reply_text("📭 Aktif takibiniz bulunmuyor.\n/monitor ile yeni takip başlatabilirsiniz.")
            return
        
        await update.message.reply_text(
            f"📋 *Aktif Takipleriniz* ({len(active_monitors)} adet):",
            parse_mode='Markdown'
        )
        
        for config in active_monitors:
            from_st = self.station_service.get_by_id(config.from_station_id)
            to_st = self.station_service.get_by_id(config.to_station_id)
            date_str = format_date_turkish(config.target_date)
            
            # Durdur butonu
            keyboard = [[InlineKeyboardButton("🛑 Bu takibi durdur", callback_data=f"stop_job_{config.job_id}")]]
            
            await update.message.reply_text(
                f"🚆 *{from_st.name} ➡ {to_st.name}*\n"
                f"📅 {date_str}\n"
                f"🕒 Son kontrol: {datetime.now().strftime('%H:%M:%S')}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    @auth_required
    async def stop_command(self, update: Update, context: CallbackContext):
        """/stop komutu - Tümünü durdur"""
        chat_id = str(update.message.chat_id)
        count = self.monitor_service.stop_all_for_user(chat_id)
        
        if count > 0:
            await update.message.reply_text(f"🛑 Tüm takipler durduruldu ({count} adet).")
        else:
            await update.message.reply_text("Aktif bir izlemeniz bulunmuyor.")
    
    # ================== TEXT MESSAGE HANDLER ==================
    
    async def text_message_handler(self, update: Update, context: CallbackContext):
        """Metin mesajı handler"""
        chat_id = str(update.message.chat_id)
        text = update.message.text.strip()
        
        # 1. Auth Kontrolü (Decorator yerine burada manual kontrol gerekebilir, çünkü şifre girişi buraya düşecek)
        if not self.auth_service.is_authenticated(chat_id):
            if self.auth_service.authenticate(chat_id, text):
                await update.message.reply_text("✅ Şifre kabul edildi! Hoş geldiniz.\nŞimdi komutları kullanabilirsiniz.")
                # Auth sonrası bilgilendirme
                await self.start_command(update, context) # Decorator olduğu için çalışır mı? Class method çağrısı sorun olabilir.
                # Direkt start mesajını atalım
                # await update.message.reply_text("Komutlar: /check, /monitor, /status")
            else:
                await update.message.reply_text("❌ Yanlış şifre. Lütfen tekrar deneyin.")
            return

        # 2. Normal akış
        session = self.sessions.get(chat_id)
        if not session or not session.state:
            # Komut algılanmadıysa ve session yoksa
            await update.message.reply_text("Bir komut girmediniz. Menü için /start yazın.")
            return
        
        if len(text) < 3:
            await update.message.reply_text(
                "⚠️ Lütfen en az 3 karakter girin.\nÖrnek: `Ank`, `İst`, `İzm`",
                parse_mode='Markdown'
            )
            return
        
        if session.state == "waiting_from":
            await self._handle_from_station_search(update, session, text)
        elif session.state == "waiting_to":
            await self._handle_to_station_search(update, session, text)
    
    async def _handle_from_station_search(self, update: Update, session: UserSession, query: str):
        """Kalkış istasyonu araması"""
        results = self.station_service.search(query)
        
        if not results:
            await update.message.reply_text(
                f"❌ *'{query}'* için istasyon bulunamadı.\nLütfen farklı bir arama terimi deneyin.",
                parse_mode='Markdown'
            )
            return
        
        keyboard = create_search_result_keyboard(results, session.action)
        await update.message.reply_text(
            f"🔍 *'{query}'* için {len(results)} sonuç bulundu:\n\nLütfen kalkış istasyonunu seçin:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _handle_to_station_search(self, update: Update, session: UserSession, query: str):
        """Varış istasyonu araması"""
        results = self.station_service.search(query, session.from_station_id)
        from_station = self.station_service.get_by_id(session.from_station_id)
        
        if not results:
            await update.message.reply_text(
                f"❌ *'{query}'* için varış istasyonu bulunamadı.\n"
                f"*{from_station.name}* istasyonundan gidilebilecek farklı bir istasyon arayın.",
                parse_mode='Markdown'
            )
            return
        
        keyboard = create_search_result_keyboard(results, session.action, session.from_station_id)
        await update.message.reply_text(
            f"✅ Kalkış: *{from_station.name}*\n\n"
            f"🔍 *'{query}'* için {len(results)} sonuç bulundu:\n\nLütfen varış istasyonunu seçin:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # ================== CALLBACK HANDLER ==================
    
    async def button_callback(self, update: Update, context: CallbackContext):
        """Button callback handler"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(query.message.chat_id)
        
        # Callback'lerde de auth kontrolü önemli
        if not self.auth_service.is_authenticated(chat_id):
            await query.message.reply_text("🔒 Oturumunuz zaman aşımına uğradı veya yetkiniz yok. Lütfen şifrenizi tekrar girin.")
            return
        
        try:
            if query.data == "cancel_search":
                self.sessions.clear(chat_id)
                await query.edit_message_text("❌ İşlem iptal edildi.")
                return
            
            # Job durdurma (status menüsünden)
            if query.data.startswith("stop_job_"):
                job_id = query.data.replace("stop_job_", "")
                if self.monitor_service.stop_monitor(job_id):
                    await query.edit_message_text(f"✅ Takip durduruldu.")
                else:
                    await query.edit_message_text(f"⚠️ Takip zaten durmuş veya bulunamadı.")
                return
            
            parts = query.data.split('_')
            prefix = parts[0]
            
            if prefix == 'from':
                await self._handle_from_station_selection(query, chat_id, parts)
            elif prefix == 'to':
                await self._handle_to_station_selection(query, chat_id, parts)
            elif prefix == 'date':
                await self._handle_date_selection(query, chat_id, parts)
            elif prefix == 'mtime':
                await self._handle_time_selection(query, chat_id, parts)
            elif prefix == 'mbiz':
                await self._handle_business_selection(query, chat_id, parts)
            elif prefix == 'mcount':
                await self._handle_passenger_count_selection(query, chat_id, parts)
        
        except Exception as e:
            print(f"Callback hatası: {e}")
            import traceback
            traceback.print_exc()
            try:
                await query.message.reply_text(f"Buton işlemi sırasında hata: {e}")
            except:
                pass
    
    async def _handle_from_station_selection(self, query, chat_id: str, parts: list):
        """Kalkış istasyonu seçimi"""
        action = parts[1]
        from_station_id = int(parts[2])
        from_station = self.station_service.get_by_id(from_station_id)
        
        session = self.sessions.get_or_create(chat_id)
        session.state = "waiting_to"
        session.action = action
        session.from_station_id = from_station_id
        
        await query.edit_message_text(
            f"✅ Kalkış: *{from_station.name}*\n\n"
            f"🔍 *Varış İstasyonu Araması*\n\n"
            f"Lütfen varış istasyonu adını yazın (en az 3 karakter).",
            parse_mode='Markdown'
        )
    
    async def _handle_to_station_selection(self, query, chat_id: str, parts: list):
        """Varış istasyonu seçimi"""
        action = parts[1]
        from_station_id = int(parts[2])
        to_station_id = int(parts[3])
        
        self.sessions.clear(chat_id)
        
        from_station = self.station_service.get_by_id(from_station_id)
        to_station = self.station_service.get_by_id(to_station_id)
        
        keyboard = create_date_keyboard(action, from_station_id, to_station_id)
        await query.edit_message_text(
            f"Kalkış: *{from_station.name}*\nVarış: *{to_station.name}*\n\nLütfen bir *tarih* seçin:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _handle_date_selection(self, query, chat_id: str, parts: list):
        """Tarih seçimi"""
        action = parts[1]
        from_station_id = int(parts[2])
        to_station_id = int(parts[3])
        date_str = parts[4]
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        from_station = self.station_service.get_by_id(from_station_id)
        to_station = self.station_service.get_by_id(to_station_id)
        date_tr_str = format_date_turkish(target_date)
        
        if action == "check":
            await query.edit_message_text(
                f"🚆 *{from_station.name}* ➡ *{to_station.name}*\n🗓 *{date_tr_str}*\n\nAPI sorgulanıyor...",
                parse_mode='Markdown'
            )
            
            # Senkron kontrol
            config = MonitorConfig(
                from_station_id=from_station_id,
                to_station_id=to_station_id,
                target_date=target_date
            )
            result = self.ticket_service.check_availability(config)
            message = format_search_result(result, from_station, to_station, target_date)
            await query.message.reply_text(message, parse_mode='HTML')
        
        elif action == "monitor":
            await query.edit_message_text(
                f"🚆 *{from_station.name}* ➡ *{to_station.name}*\n🗓 *{date_tr_str}*\n\n⏳ Sefer saatleri alınıyor...",
                parse_mode='Markdown'
            )
            
            # Sefer saatlerini al
            train_times = self.ticket_service.get_train_times(from_station_id, to_station_id, target_date)
            
            if not train_times:
                await query.edit_message_text(
                    f"❌ *{from_station.name}* ➡ *{to_station.name}*\n🗓 *{date_tr_str}*\n\nBu tarihte sefer bulunamadı.",
                    parse_mode='Markdown'
                )
                return
            
            # Session'a kaydet
            session = self.sessions.get_or_create(chat_id)
            session.state = "selecting_times"
            session.action = "monitor"
            session.from_station_id = from_station_id
            session.to_station_id = to_station_id
            session.target_date = target_date
            session.available_times = train_times
            session.selected_times = [t.time for t in train_times]
            
            # Saatleri göster
            times_info = "\n".join([f"• {t.time} - {t.train_name}" for t in train_times[:10]])
            keyboard = create_time_selection_keyboard(train_times, session.selected_times)
            
            await query.edit_message_text(
                f"🚆 *{from_station.name}* ➡ *{to_station.name}*\n🗓 *{date_tr_str}*\n\n"
                f"*Mevcut Seferler:*\n{times_info}\n\n"
                f"⏰ *İzlemek istediğiniz saatleri seçin:*\n(Seçili olanlar ✅ ile gösterilir)",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    async def _handle_time_selection(self, query, chat_id: str, parts: list):
        """Saat seçimi callback"""
        session = self.sessions.get(chat_id)
        if not session or session.state != "selecting_times":
            await query.edit_message_text("❌ Oturum süresi doldu. Lütfen /monitor ile tekrar başlayın.")
            return
        
        sub_action = parts[1]
        
        if sub_action == "toggle":
            time_str = parts[2]
            if time_str in session.selected_times:
                session.selected_times.remove(time_str)
            else:
                session.selected_times.append(time_str)
            
            keyboard = create_time_selection_keyboard(session.available_times, session.selected_times)
            await query.edit_message_reply_markup(reply_markup=keyboard)
        
        elif sub_action == "all":
            if len(session.selected_times) < len(session.available_times):
                session.selected_times = [t.time for t in session.available_times]
            else:
                session.selected_times = []
            
            keyboard = create_time_selection_keyboard(session.available_times, session.selected_times)
            await query.edit_message_reply_markup(reply_markup=keyboard)
        
        elif sub_action == "done":
            if not session.selected_times:
                await query.answer("⚠️ En az bir saat seçmelisiniz!", show_alert=True)
                return
            
            session.state = "selecting_business"
            keyboard = create_business_keyboard()
            
            from_station = self.station_service.get_by_id(session.from_station_id)
            to_station = self.station_service.get_by_id(session.to_station_id)
            date_tr_str = format_date_turkish(session.target_date)
            times_str = ", ".join(sorted(session.selected_times))
            
            await query.edit_message_text(
                f"🚆 *{from_station.name}* ➡ *{to_station.name}*\n🗓 *{date_tr_str}*\n"
                f"⏰ Saatler: {times_str}\n\n"
                f"💼 *Business sınıfını dahil etmek ister misiniz?*",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    async def _handle_business_selection(self, query, chat_id: str, parts: list):
        """Business seçimi callback"""
        session = self.sessions.get(chat_id)
        if not session or session.state != "selecting_business":
            await query.edit_message_text("❌ Oturum süresi doldu. Lütfen /monitor ile tekrar başlayın.")
            return
        
        session.include_business = parts[1] == "yes"
        session.state = "selecting_count"
        
        keyboard = create_passenger_count_keyboard()
        
        from_station = self.station_service.get_by_id(session.from_station_id)
        to_station = self.station_service.get_by_id(session.to_station_id)
        date_tr_str = format_date_turkish(session.target_date)
        times_str = ", ".join(sorted(session.selected_times))
        biz_str = "Dahil" if session.include_business else "Hariç"
        
        await query.edit_message_text(
            f"🚆 *{from_station.name}* ➡ *{to_station.name}*\n🗓 *{date_tr_str}*\n"
            f"⏰ Saatler: {times_str}\n💼 Business: {biz_str}\n\n"
            f"👥 *Kaç kişilik yer arıyorsunuz?*\n(En az bu kadar boş yer olunca bildirim alacaksınız)",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _handle_passenger_count_selection(self, query, chat_id: str, parts: list):
        """Kişi sayısı seçimi callback"""
        session = self.sessions.get(chat_id)
        if not session or session.state != "selecting_count":
            await query.edit_message_text("❌ Oturum süresi doldu. Lütfen /monitor ile tekrar başlayın.")
            return
        
        session.min_seats = int(parts[1])
        
        from_station = self.station_service.get_by_id(session.from_station_id)
        to_station = self.station_service.get_by_id(session.to_station_id)
        date_tr_str = format_date_turkish(session.target_date)
        
        await query.edit_message_text(
            f"✅ *İzleme ayarları tamamlandı!*\n\n"
            f"🚆 *{from_station.name}* ➡ *{to_station.name}*\n🗓 *{date_tr_str}*\n\n"
            f"İzleme başlatılıyor...",
            parse_mode='Markdown'
        )
        
        # MonitorConfig oluştur
        config = MonitorConfig(
            from_station_id=session.from_station_id,
            to_station_id=session.to_station_id,
            target_date=session.target_date,
            selected_times=session.selected_times,
            include_business=session.include_business,
            min_seats=session.min_seats
        )
        
        # Session temizle
        self.sessions.clear(chat_id)
        
        # Monitor başlat
        def on_change(cid: str, result, changes: dict):
            self._handle_monitor_change(cid, result, changes, from_station, to_station)
        
        def on_start(cid: str, cfg: MonitorConfig):
            msg = format_monitor_start(cfg, from_station, to_station)
            if self._send_message:
                self._send_message(cid, msg)
        
        self.monitor_service.start_monitor(chat_id, config, on_change, on_start)
    
    def _handle_monitor_change(self, chat_id: str, result, changes: dict, from_station, to_station):
        """Monitor değişiklik callback'i"""
        if not self._send_message:
            return
        
        change_type = changes.get("type", "")
        
        if change_type == "first_check":
            if changes.get("has_availability"):
                msg = "🎫 İLK KONTROL - BİLET DURUMU:\n\n"
                msg += format_search_result(result, from_station, to_station, result.trains[0].train.departure_time if result.trains else None)
                self._send_message(chat_id, msg)
            else:
                self._send_message(chat_id, "ℹ️ İlk kontrol tamamlandı. Şu anda kriterlere uygun yer bulunmuyor. Yer açıldığında bildirim alacaksınız.")
        
        elif change_type == "new_availability":
            msg = format_change_notification(result, changes)
            self._send_message(chat_id, msg)
        
        elif change_type == "all_gone":
            self._send_message(chat_id, "❌ Daha önce uygun olan yerler doldu. Yeni yer açılmasını bekliyorum...")
