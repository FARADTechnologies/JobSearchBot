# ROADMAP.md — JobSearchBot / Startup Yol Haritası

> Yaşayan doküman. Vizyon: [VISION.md](VISION.md) · Mimari: [ARCHITECTURE.md](ARCHITECTURE.md)
> Son güncelleme: 2026-08-15

## 🎯 ŞU ANKİ ODAK: Hesen'in kişisel iş-bulma sistemi (startup ertelendi)

Startup/çok-kullanıcı/CV-havuzu tarafı **bilerek ertelendi**. Şu an tek amaç: Hesen'e
iş bulan kişisel bir sistem. İki canlı akış var:

- **🔔 Azerbaycan işleri** (jobsearch.az → robotik/STEAM eşleştirme) → DM, günde 5x
- **🌍 Global remote işler** (Adzuna + 4 bedava board → LLM-judge → skor + "neden uygun")
  → "Xarici İşlər Remote" grubu, saatlik

### Yapılacaklar (öncelik sırası)

0. **DOĞRULA (önce bu):** RemoteJobs workflow'unu tetikle, grup LLM-seçili skorlu işler
   alıyor mu, kalite iyi mi, US-only gitmiş mi — gerçek çıktıyı gör. Kötüyse üstüne bir
   şey inşa etme.
1. **TUNE:** çıktıya göre profil spec'i, skor eşiği, hacim, maaş tabanını ayarla.
2. **👍/👎 geri bildirim** (odaklı iş): yüksek-skor işleri butonla ayrı gönder →
   tıklamayı işle → `data/remote_feedback.json` → beğenilmeyeni LLM prompt'una besle (moat).
3. **Havuzu büyüt:** Jooble (60+ ülke, bedava key talep) + Careerjet + The Muse.
4. **Oto-başvuru (LLM ile hedefli):** önce mail-tabanlı, sonra web form/ATS doldurma.
5. **Başvuru takipçisi** (oto-başvuruyla birlikte).

### Bitti (bu oturumlarda)
Adzuna havuzu · Gemini LLM-judge (batch, retry, skor + why-fits) · ayrı grup routing ·
saatlik remote workflow · geo-eligibility (LLM) · dedup · maaş filtresi · digest modu ·
güvenlik taraması (repo public, temiz).

---

## Durum anlık görüntüsü (startup — ERTELENDİ)

| Katman | Durum |
|---|---|
| Scraper (jobsearch.az, tam sayfalama + retry) | ✅ Canlı, 3+ haftadır stabil |
| GitHub Actions (günde 5x, bedava) | ✅ Canlı |
| Legacy tek-kullanıcı bildirim (Hesen'in profili) | ✅ Canlı |
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
  internship, ödənişli`. Kusurlu ama Hesen'in kişisel ihtiyacı için hemen çalışır.
- **Doğru (LLM çıkarımı):** yukarıdaki yapılandırılmış alanlar. Çok kaynakta tutarlı,
  yanlış-etiketli ilanları da yakalar.

### Hesen'in kişisel profili (bu özelliğin ilk test kullanıcısı)
- Aranan: **part-time VEYA remote** (ikisi birden ideal), alan fark etmez
- Remote ise: AI ile yürütülebilir işler de olur (yani alan dışı da kabul)
- Ödənişli təcrübə de dahil

---

## ÇOK KAYNAK: Azerbaycan iş siteleri (popülerlikten aza doğru)

| # | Site | Tip | Not |
|---|---|---|---|
| 1 | **HelloJob.az** | Kendi HR müşterileri | "Azerbaycan #1" iddiası, büyük hacim |
| 2 | **JobSearch.az** | Kendi müşterileri | ✅ Zaten entegre (API çözüldü) |
| 3 | **BirJob.com** | **Agregatör — RESMİ API!** | ⭐⭐ 91 kaynağı tekilleştirip tek API'den veriyor, ~12.257 ilan. Aşağıya bak. |
| 4 | **Boss.az** | Agregatör | Büyük |
| 5 | **Jooble.az** | Agregatör | Global Jooble'ın AZ kolu |
| 6 | **AZJOB.az** | İlan sitesi | |
| 7 | **İşəQəbul.az** | İlan sitesi | "gerçek şirketlerden" |
| 8 | **JobU.az / isbu.az** | İlan sitesi | Daha küçük |

**Remote'a özel (global, ToS ağır):** LinkedIn, We Work Remotely, Remote.co, Arc.dev,
Himalayas, DailyRemote, Workana. Hesen "homora gibi AI ile remote" istediği için bunlar
onun kişisel akışı için değerli, ama scraping'i risklidir — sonraki aşama.

### ⭐ BirJob API — oyun değiştirici (2026-08 keşfi)
`https://www.birjob.com/api/v1` — resmi geliştirici API'si (Bearer token, kayıtta otomatik
anahtar `/developers/keys`). Bizim 8 adapter yazmamız yerine **91 kaynağı tekilleştirilmiş
şekilde tek entegrasyonla** verir. Kritik: yanıt alanları tam da istediklerimiz —
`employment_type` (Full/Part-time/Contract/Internship/Freelance), `work_type`
(Onsite/Hybrid/Remote) + `is_remote`, `salary_from/to`, `description_text`,
`requirements_text`, `apply_link`, `source`, `deadline_at`, `contact_email/phone`.
`from_id` ile artımlı senkron. Günde 3x GitHub Actions cron ile taranıyor.

**Bu, remote/part-time özelliğinin yapılandırılmış tarafını neredeyse hazır çözüyor**
(is_remote / employment_type alanları). LLM sadece bunların eksik/yanlış olduğu ilanlar
için gerekir.

**Riskler:**
- **Ücretli/kotalı** (aylık "unit" kotası, plana bağlı; bedava tier açık değil — kayıtta
  kontrol et). /v1/jobs = 1 unit (arama 5). Tam senkron ~123 istek; `from_id` ile ucuz.
- **Tek nokta bağımlılığı** + BirJob'un kendisi de bir AZ iş platformu (iOS app) =
  potansiyel rakip. Bizi keserse çok-kaynak çöker.
- **Mitigasyon:** BirJob'u kapsam genişletme + doğrulama olarak kullan, kendi jobsearch.az
  scraper'ımızı birincil/yedek tut, uzun vadede en büyük 2-3 site için kendi adapter'lerimiz.

### Strateji (güncel)
- **Faz A:** BirJob API'yi bir kaynak adapter'ı olarak ekle (bedava kota yeterse) → anında
  91 kaynak + yapılandırılmış remote/part-time alanları.
- **Faz B:** en büyük siteler için (HelloJob, Boss) kendi doğrudan adapter'lerimiz (bağımlılık
  azaltma).
- **Dedup şart** (BirJob kendi içinde tekilleştiriyor ama biz + jobsearch.az birleşince tekrar
  gerekir): fingerprint/embedding.
- **ToS/hukuk:** BirJob API'si resmi (yeşil); doğrudan scraping'de yavaş + robots.txt.

---

## YENİ (ZORUNLU) ÖZELLİK: Dolandırıcılık / sahte ilan filtresi

**Neden zorunlu:** Remote iş dolandırıcılığı patlıyor (2026'da ~521M$ zarar, Mayıs-Temmuz
arası %1000 artış). Özellikle remote/part-time = en yüksek dolandırıcılık yoğunluğu. Bizim
için normal bir kullanıcıdan **daha kritik**, çünkü Faz 2'de **oto-başvuru** var — sahte bir
ilana otomatik başvurmak = kullanıcının CV'sini/kişisel verisini dolandırıcıya göndermek.

**Kırmızı bayraklar (LLM-judge / kural katmanına eklenecek):**
- Peşin ödeme / "kayıt ücreti" isteyen
- Gerçekçi olmayan yüksek maaş, aşırı belirsiz iş tanımı, aciliyet baskısı
- Sadece WhatsApp/Telegram'a yönlendiren, kurumsal e-posta yerine gmail/şahsi iletişim
- Erken aşamada pasaport/banka/şəxsiyyət vəsiqəsi isteyen
- Şirket adı doğrulanamıyor / kariyer sayfası yok

**Uygulama:** çıkarım aşamasına `fraud_risk`: low|medium|high alanı; high olanlar
bildirilmez veya "⚠️ şüpheli" etiketiyle bildirilir; oto-başvuru **asla** high'a yapmaz.

**BirJob'un kendisi güvenli mi?** Evet — BirJob geçişli (pass-through) agregatör: ilanı
kaynağından listeler, kaynağı gösterir, başvuru **orijinal sitede** yapılır; CV toplamaz.
Yani BirJob veri çalan taraf değil. Risk, alttaki 91 kaynağın içindeki sahte ilanlarda —
onu da yukarıdaki filtre ele alır.

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
