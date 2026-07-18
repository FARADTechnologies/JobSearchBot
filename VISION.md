# JobSearchBot — Vizyon ve Startup Fikri

> Bu dosya projenin **amacını, tüm özelliklerini ve fazlarını** saklar. Unutmamak için.
> Son güncelleme: 2026-07-14

---

## 1. Amaç

İş arayan kişinin yerine **7/24 tarayan, anlayan, seçen ve (istenirse) başvuran bir AI ajanı**.

**Problem:** İnsanlar iş arıyor ama 7/24 her siteyi kontrol edemiyor. İlan çok, bazıları
hepsini göremiyor, bazıları üşeniyor ve fırsatları kaçırıyor.

**Çözüm:** Kullanıcı kendi işini yaparken bot onun için Azerbaycan'daki tüm aktif ilanları
izler, profiline uyanları bulur, bildirir ve izin verirse başvurur.

**Fırsat:** Azerbaycan'da bu işi yapan yerel bir rakip yok.

## 2. Kime hizmet ediyor

- **İş arayanlar (Azerbaycan)** → kullanıcı kazanım motoru (ucuz/bedava)
- **İşverenler** → asıl gelir kaynağı (Faz 3)

## 3. Ürün ve özellikler (tam liste)

### Faz 1 — Çok kullanıcılı akıllı bildirim (ücretsiz)
- Kullanıcı programa girer, **CV yükler**
- **Mail ilişkilendirme**
- **Manuel filtre**: hangi tür iş, çalışma saati, maaş vb.
- **veya** uygulamadaki **AI ile chat'te konuşarak** filtreyi kurdurma
- **veya tam otonom mod**: AI CV'yi okuyup neyin uygun olduğuna kendisi karar verir
- Azerbaycan'daki **tüm aktif ilanlar** taranır (çok kaynak: jobsearch.az + benzeri siteler)
- **Bildirim sıklığını kullanıcı seçer** (ör. 2-3 saatte bir)
- Her ilanda **son başvuru tarihi**

### Faz 2 — Otomatik başvuru
- **Güven merdiveni**: sadece bildirim → tek-dokunuş onay → tam otonom
- Uygun her işe **otomatik mail**
- İşe **özel motivasyon mektubu** (AI yazar)
- Sadece CV isteniyorsa CV, yazı isteniyorsa yazı gönderir
- Sitede **form doldurulması gerekiyorsa doldurur**
- Mektup kaynağı seçeneği: kullanıcı önceden kendi yazar / **local LLM** / bizim AI / dış API
  (kullanıcı onaylar)
- Başvurular **kullanıcının kendi hesabından** gider (tespit edilebilir bir kalıp yok)

### Faz 3 — CV Havuzu (CV House)
- Kullanıcı **kendi isteği ve onayıyla** CV'sini havuza koyar (bir ilan/reklam gibi)
- Şirketler uygun aday ararken havuza bakar
- **AI en uygun adayları seçer/sıralar**
- **İşverenler öder** → asıl gelir

## 4. İş modeli

| Taraf | Fiyat | Rolü |
|---|---|---|
| İş arayan | ucuz/bedava (ör. 5 AZN/ay) | büyüme motoru |
| İşveren | asıl ücret (aday erişimi / abonelik) | **gelir** |

Bu aslında Indeed/LinkedIn modeli: **iş arayana bedava, parayı işveren öder.**

## 5. Ölçülecek 2 metrik (gerisi gürültü)

1. **Faz 1 — geri dönüş:** kullanıcı 3-7 gün sonra hâlâ kullanıyor mu?
2. **Faz 2 — cevap oranı:** oto-başvuru gerçekten mülakat/cevap getiriyor mu?

## 6. Riskler (unutulmasın)

- **Başarı = churn.** Kullanıcı 1 ayda iş bulup gider → ömür boyu değeri ≈ 1 ay.
  Büyüme **sadece** sürekli yeni kullanıcıyla olur → viral/ağızdan ağıza tasarla.
- **İki taraflı pazar (Faz 3):** boş havuza işveren para vermez → önce iş arayan tarafını kazan.
- **CV = kişisel veri:** opt-in şart; sızıntı = güven ve hukuk felaketi.
- **LLM maliyeti** birim ekonomiyi patlatabilir → kullanıcının kendi anahtarı / local LLM.
- **AI-native tek başına moat değil.** Gerçek moat: CV havuzu + işe-alım sonuçlarından öğrenen
  **veri döngüsü**.
- **Platform/ToS riski:** siteler engelleyebilir → çok kaynak bu riski azaltır.

## 7. Konumlanma: AI-native

AI çıkarsa ürün çöker (CV'yi anlama, ilanları kavrama, mektup yazma, otonom başvuru).
Rakipler **kelime veritabanı**, biz **ajanız**. Mevcut kod hâlâ kural-tabanlı (regex);
AI-native çekirdeğe geçiş, gerçek kullanıcı geldikten sonra yapılacak.

## 8. Bugünkü durum

Çalışan **tek kullanıcılık** Telegram botu:
- GitHub Actions'ta günde 5 kez (Bakü 09/12/15/18/21), ücretsiz, kimsenin bilgisayarında değil
- jobsearch.az'daki **~2700 ilanın tamamını** tarıyor (API + sayfalama + retry)
- CV profiline göre eşleştirip Telegram'a **tek toplu mesaj** atıyor (son başvuru tarihleriyle)

**Sıradaki adım:** Faz 1 — botu çok kullanıcılı hale getirmek.
