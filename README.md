# JobSearchBot

JobSearch.az üzerindeki **tüm aktif ilanları** tarayıp kullanıcının profiline uygun
işleri Telegram'a bildiren bot. Vizyon ve yol haritası: [VISION.md](VISION.md) ·
Teknik mimari: [ARCHITECTURE.md](ARCHITECTURE.md)

## Nasıl çalışıyor

- **GitHub Actions** günde 5 kez çalıştırır (Bakü 09/12/15/18/21) — hiçbir yerel
  makine gerekmez.
- Scraper, sitenin JSON API'sini sayfalayarak ~2700 ilanın tamamını çeker
  (retry/backoff ile).
- İki akış vardır:
  - **Legacy (tek kullanıcı):** `.env`/Secrets'teki `TELEGRAM_CHAT_ID` için
    kural-tabanlı sınıflandırma (`jobbot/classifier.py`).
  - **Faz 1 (çok kullanıcı, Supabase):** kullanıcılar bota `/start` deyip CV (PDF)
    yükler; her kullanıcı kendi profiline göre eşleşme alır. İlan korpusu tüm
    kullanıcılar için ortaktır ve bir kez analiz edilip cache'lenir.

## Kurulum (geliştirme)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # değerleri doldur
.\.venv\Scripts\python.exe -m jobbot --dry-run
```

## Faz 1 kurulumu (çok kullanıcı)

1. Supabase projesi oluştur → `supabase/migrations/001_init.sql` içeriğini
   SQL Editor'de çalıştır.
2. `.env` (yerel) ve GitHub Actions Secrets'e ekle:
   - `SUPABASE_URL`, `SUPABASE_SECRET_KEY`
   - `GROQ_API_KEY` (opsiyonel — yoksa CV profili heuristik çıkarılır)
3. Bot çalıştığında gelen `/start` + CV yüklemelerini her cron turunda işler.

Gizlilik kuralı: **CV'ler kişisel veridir** — yalnızca veriyi eğitimde kullanmayan
sağlayıcılara gönderilir (Groq/Cohere). Ayrıntı: [ARCHITECTURE.md](ARCHITECTURE.md).

## GitHub Secrets (Actions)

| Secret | Zorunlu | Açıklama |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | BotFather token'ı |
| `TELEGRAM_CHAT_ID` | ✅ | Legacy tek-kullanıcı chat id |
| `SUPABASE_URL` | Faz 1 için | Proje URL'i |
| `SUPABASE_SECRET_KEY` | Faz 1 için | service_role secret key |
| `GROQ_API_KEY` | opsiyonel | CV profil çıkarımı (LLM) |
| `OPENAI_API_KEY` | opsiyonel | Legacy AI sınıflandırma |
