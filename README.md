# TCDD E-Bilet Takip Botu 🚂

TCDD Taşımacılık tren biletlerini otomatik olarak takip eden, boş yer açıldığında Telegram üzerinden anlık bildirim gönderen gelişmiş, modüler bir bot.

## 🌟 Özellikler

- **Çoklu İzleme (Multi-Task):** Aynı anda birden fazla farklı seferi (farklı tarihler veya rotalar) takip edebilirsiniz.
- **Kullanıcı Yetkilendirme (Auth):** Botu şifre ile koruyabilir, sadece yetkili kişilerin kullanmasını sağlayabilirsiniz.
- **Gelişmiş Filtreleme:**
  - ⏰ Saat aralığı seçimi
  - 💼 Business / Ekonomi vagon seçimi
  - 👥 Kişi sayısı filtresi (Örn: En az 3 koltuk varsa haber ver)
- **Akıllı Bildirimler:**
  - İlk kontrol sonucu
  - Yeni yer açıldığında bildirim
  - Yerler tükendiğinde bildirim
- **Dinamik Yapı:** TCDD API token değişimlerine karşı dirençli (Otomatik Token Yenileme).
- **Yönetim Paneli:** `/status` komutu ile aktif takiplerinizi görebilir ve tek tek durdurabilirsiniz.

## 🛠️ Kurulum

### Gereksinimler
- Python 3.10+
- Telegram Bot Token (BotFather'dan alınmış)

### 1. Projeyi Hazırlayın
Projeyi indirin ve gerekli kütüphaneleri kurun:
```bash
pip install -r requirements.txt
```

### 2. Konfigürasyon
`.env.example` dosyasının adını `.env` olarak değiştirin ve düzenleyin:
```ini
# BotFather'dan alınan token
TELEGRAM_API_TOKEN=123456:ABC-DEF...

# Botu kullanmak için gerekli şifre
BOT_PASSWORD=gizli_sifreniz
```

### 3. Çalıştırma
Botu başlatın:
```bash
python src/main.py
```

## 🐳 Docker ile Kurulum

Hazır Dockerfile ile konteyner içinde çalıştırabilirsiniz:

```bash
# İmajı oluşturun
docker build -t ebilet-bot .

# Konteyneri çalıştırın
docker run -d --name my-bot --env-file .env ebilet-bot
```

## 📱 Kullanım

Telegram'dan bota mesaj atın ve şifrenizi girin. Ardından şu komutları kullanabilirsiniz:

| Komut | Açıklama |
|-------|----------|
| `/start` | Botu ve menüyü başlatır. |
| `/monitor` | **Yeni bir takip görevi oluşturur.** (Sınırsız sayıda ekleyebilirsiniz) |
| `/check` | Tek seferlik anlık sorgulama yapar. |
| `/status` | **Aktif takiplerinizi listeler** ve yönetmenizi sağlar. |
| `/stop` | Kendinize ait **tüm** takipleri durdurur. |

## 🏗️ Proje Mimarisi

Bu proje **Modüler OOP (Nesne Yönelimli Programlama)** prensiplerine göre tasarlanmıştır:

```
src/
├── api/          → TCDD API iletişimi ve Token yönetimi
├── models/       → Veri yapıları (Station, Train, Config)
├── services/     → İş mantığı (Ticket, Station, Monitor, Auth)
├── interfaces/   → Telegram Bot entegrasyonu (Handlers, UI)
└── utils/        → Yardımcı araçlar
```

- **Veritabanı:** Kullanıcı yetkilendirmesi için SQLite (`users.db`) kullanılır.
- **Concurrency:** Her izleme görevi ayrı bir `Thread` üzerinde, birbirinden bağımsız çalışır.

## 📝 Lisans
MIT
