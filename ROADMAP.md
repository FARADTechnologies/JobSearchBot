# ROADMAP.md — JobSearchBot / Startup Yol Haritası

> Yaşayan doküman. Vizyon: [VISION.md](VISION.md) · Mimari: [ARCHITECTURE.md](ARCHITECTURE.md)
> Son güncelleme: 2026-08-06

## Durum anlık görüntüsü

| Katman | Durum |
|---|---|
| Scraper (jobsearch.az, tam sayfalama + retry) | ✅ Canlı, 3+ haftadır stabil |
| GitHub Actions (günde 5x, bedava) | ✅ Canlı |
| Legacy tek-kullanıcı bildirim (the founder'in profili) | ✅ Canlı |
| Faz 1 çok-kullanıcı temeli (Supabase şema, onboarding, CV, kişiye özel eşleştirme) | 🟡 **Kod hazır**, devreye alma bekliyor |
| — Supabase şema SQL çalıştırma | ⛔ Kullanıcı yapacak (SQL Editor) |
| — GitHub Secrets (SUPABASE_URL/KEY) | ⛔ Kullanıcı ekleyecek |
| — Groq anahtarı (CV profil çıkarımı) | ⛔ Hesap sorunu → şimdilik heuristik |
| AI-native eşleştirme motoru (embedding→rerank→LLM-judge) | ⬜ Tasarlandı, kodlanmadı |
| Faz 2 oto-başvuru | ⬜ |
| Faz 3 CV havuzu (işveren geliri) | ⬜ |

## Fazlar (sıra)

**Faz 1 — Çok kullanıcılı akıllı bildirim** (şu an burada)
1. Devreye alma: şema + secrets + (opsiyonel) Groq
2. AI-native eşleştirme motoru: her ilan/CV bir kez LLM ile İngilizce yapılandırılmış
   çıkarım + BGE-M3 embedding → pgvector → hard filtre → hibrit getirme → rerank → LLM-judge
3. **Yeni: remote/part-time/təcrübə arama** (aşağıda ayrı bölüm)
4. Çok kaynak (aşağıda ayrı bölüm)
5. Ölçüm: golden set + nDCG + online CTR/retention

**Faz 2 — Otomatik başvuru** (güven merdiveni: bildirim → tek-dokunuş → otonom)

**Faz 3 — CV havuzu** (opt-in, işveren AI ile aday arar, **asıl gelir**)

---

## YENİ ÖZELLİK: remote / part-time / ödənişli təcrübə araması

### Problem
Sitelerin yapılandırılmış `job_type` filtresi bunları çoğu zaman **kaçırıyor**, çünkü:
1. İşveren yapılandırılmış alanı yanlış/eksik dolduruyor
2. "remote / part-time" bilgisi çoğu zaman sadece **ilan metninde** geçiyor
3. Azerbaycan'da "təcrübə (staj)" ilanları bazen **ödənişli** ve remote/part-time olabiliyor
   — ama bunu anlamak için açıklamayı okumak lazım

### Çözüm — bu tam olarak AI-native çıkarım motorunun işi
Ayrı bir sistem gerekmiyor. LLM her ilanı zaten bir kez okuyor (ARCHITECTURE.md); çıkarım
şemasına şu alanları ekliyoruz:
- `work_mode`: remote | hybrid | onsite | unknown
- `employment_type`: full_time | part_time | contract | internship | unknown
- `is_paid`: true | false | unknown   (təcrübə ilanları için kritik)
- `remote_eligibility`: "AZ-only" | "global" | unknown

Sonra kullanıcı bunları **hard filtre** olarak seçer (SQL WHERE). Kullanıcının istediği
"NLP" tam olarak bu çıkarım aşaması.

### İki seviye
- **Hızlı (LLM'siz, bugün yapılabilir):** başlık+açıklamada çok dilli anahtar-kelime ağı:
  `remote, uzaqdan, distant, work from home, evdən, onlayn, part-time, part time,
  yarım ştat, natamam iş günü, natamam iş vaxtı, saatlıq, freelance, təcrübə, staj,
  internship, ödənişli`. Kusurlu ama the founder'in kişisel ihtiyacı için hemen çalışır.
- **Doğru (LLM çıkarımı):** yukarıdaki yapılandırılmış alanlar. Çok kaynakta tutarlı,
  yanlış-etiketli ilanları da yakalar.

### the founder'in kişisel profili (bu özelliğin ilk test kullanıcısı)
- Aranan: **part-time VEYA remote** (ikisi birden ideal), alan fark etmez
- Remote ise: AI ile yürütülebilir işler de olur (yani alan dışı da kabul)
- Ödənişli təcrübə de dahil

---

## ÇOK KAYNAK: Azerbaycan iş siteleri (popülerlikten aza doğru)

| # | Site | Tip | Not |
|---|---|---|---|
| 1 | **HelloJob.az** | Kendi HR müşterileri | "Azerbaycan #1" iddiası, büyük hacim |
| 2 | **JobSearch.az** | Kendi müşterileri | ✅ Zaten entegre (API çözüldü) |
| 3 | **BirJob.com** | **Agregatör (50+ kaynak, 8000+ ilan)** | En geniş kapsam. Ama "scraper'ı scrape etmek" — kırılgan + ToS riski. Değerlendir. |
| 4 | **Boss.az** | Agregatör | Büyük |
| 5 | **Jooble.az** | Agregatör | Global Jooble'ın AZ kolu |
| 6 | **AZJOB.az** | İlan sitesi | |
| 7 | **İşəQəbul.az** | İlan sitesi | "gerçek şirketlerden" |
| 8 | **JobU.az / isbu.az** | İlan sitesi | Daha küçük |

**Remote'a özel (global, ToS ağır):** LinkedIn, We Work Remotely, Remote.co, Arc.dev,
Himalayas, DailyRemote, Workana. the founder "homora gibi AI ile remote" istediği için bunlar
onun kişisel akışı için değerli, ama scraping'i risklidir — sonraki aşama.

### Strateji
- Her kaynak = bir **adapter** (jobsearch.az'daki `scraper.py` deseni). Ortak `Job` modeline
  normalize et.
- **Dedup şart** (aynı ilan birden çok sitede): fingerprint (şirket+başlık+normalize) veya
  embedding benzerliği.
- **Sıra:** önce HelloJob + Boss (doğrudan, en büyük yerli hacim), BirJob'u ayrı değerlendir
  (tek entegrasyonla 50+ kaynak cazip ama bağımlılık riski).
- **ToS/hukuk:** yavaş tara, robots.txt, login arkasına geçme (ARCHITECTURE.md riskleri).

---

## Fikir / İdeya havuzu (backlog, sıralı değil)

- **Otomatik mail** (planned-email-feature): uygun işlere Telegram + mail
- **"Neden uygun?" açıklaması** her eşleşmede (güven → churn azaltır)
- **Kullanıcı geri bildirimi** (👍/👎 butonları) → `matches` feedback → veri döngüsü → moat
- **CV kalite/eksik uyarısı** (parsing ~%75-85, kullanıcıya "profilini kontrol et")
- **Çoklu profil**: bir kullanıcı hem alanında hem "remote AI işi" için ayrı filtre
- **Maaş aralığı çıkarımı** (çoğu ilanda gizli; metinden tahmin)
- **Bildirim özeti**: günlük/haftalık tek digest opsiyonu (bildirim yorgunluğu)
- **Dil normalizasyonu**: çıkarımı İngilizce'ye çevir (Azerice düşük-kaynak riskini bypass)
- **İşveren tarafı MVP** (Faz 3): şirket "böyle birini arıyorum" → AI aday sıralar
- **Web/mobil arayüz** (Telegram'dan sonra)
- **Anahtar rotasyonu**: Supabase secret + Telegram token chat'e yapıştırılmıştı → döndür

## Bilinen teknik borç / riskler
- GitHub Actions ara sıra "runner not acquired" (altyapı, kendi düzelir — kod değil)
- Tek kaynağa bağımlılık (çok kaynak bunu azaltacak)
- Groq hesabı bloklu → CV profili şimdilik heuristik (LLM'e geçince kalite artar)
- CV = kişisel veri → gizlilik/KVK (Faz 3 öncesi hukuki danışma)
