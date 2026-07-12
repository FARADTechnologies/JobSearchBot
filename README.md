# JobSearchBot

JobSearch.az uzerinden yeni ilanlari kontrol eden, STEAM/STEM, robotika, kodlama ve teknoloji egitmenligi ile alakali isleri bulan ve Telegram'a bildiren Python botu.

Bot iki seviyeli calisir:

1. Hizli filtre: Baslik, sirket ve ilan metninde genis anahtar kelime/sinyal arar.
2. Akilli siniflandirma: `OPENAI_API_KEY` varsa ilani kullanici profiline gore AI ile degerlendirir.

API anahtari yoksa bot yine calisir, fakat sadece yerel kural tabanli karar verir.

## Kurulum

```powershell
cd "C:\Users\ACER\Documents\My Projects\JobSearchBot"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

`.env` icinde en az sunlari doldur:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

OpenAI ile daha akilli karar vermesini istiyorsan:

```env
OPENAI_API_KEY=...
```

## Calistirma

```powershell
.\run.ps1
```

Test icin Telegram gondermeden sadece tarama ve karar ciktilarini gormek istersen:

```powershell
.\.venv\Scripts\python.exe -m jobbot --dry-run
```

## Windows Task Scheduler

Task Scheduler'da yeni task olustur:

- Program/script: `powershell.exe`
- Arguments: `-ExecutionPolicy Bypass -File "C:\Users\ACER\Documents\My Projects\JobSearchBot\run.ps1"`
- Start in: `C:\Users\ACER\Documents\My Projects\JobSearchBot`

15-30 dakikada bir calistirmak yeterlidir. Bot `data/seen_jobs.json` dosyasina gordugu ilanlari yazar, ayni ilani tekrar gondermez.

## Hedef Profil

Ilgili sayilan isler:

- STEAM/STEM muellimliyi
- Robotika muellimliyi veya telimcisi
- Kodlama/proqramlasdirma/informatika muellimi
- Usaqlar ve yeniyetmeler ucun texnologiya tehsili
- Mekteb, kurs, academy, tehsil merkezi rolleri

Ilgisiz sayilan isler:

- Sadece software developer isleri
- IT support/admin isleri
- Satis, call center, ofis meneceri
- Tehsil veya telimle alakasi olmayan muhendislik rolleri
