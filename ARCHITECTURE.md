# ARCHITECTURE.md — Eşleştirme Motoru Mimarisi (kilitlendi: 2026-07-14)

> İki bağımsız araştırma (Claude Code + Claude Research) aynı mimaride birleşti.
> Bu doküman kararları sabitler. Değişiklik ancak golden-set ölçümüyle yapılır.
> Vizyon için: [VISION.md](VISION.md)

## Temel ilkeler

1. **Bir kez analiz et, sakla.** Her ilan ve her CV tam olarak BİR kez LLM'den geçer
   (yapılandırılmış JSON çıkarım + embedding), sonucu DB'de durur. İlan analizleri
   TÜM kullanıcılar için ortaktır — ekonomiyi kurtaran şey budur.
2. **Kademeli pipeline.** Ucuz ve geniş başla, pahalı ve dar bitir. LLM asla
   2700 ilana dokunmaz; sadece kısa listeye dokunur.
3. **Ölçmeden değiştirme.** Her pipeline değişikliği golden set'te puanlanır.
   "İyi çalışıyor hissi" veri değildir.

## Pipeline

```
[Aşama 0 — Alım (her belge 1 kez)]
  İlan → LLM çıkarım (JSON: başlık, beceriler, deneyim, dil, yer, maaş; İngilizce)
       → BGE-M3 embedding → Supabase pgvector (jobs tablosu)
  CV   → parse (PDF; görsel PDF için OCR fallback) → LLM çıkarım (JSON, İngilizce)
       → BGE-M3 embedding → Supabase pgvector (cvs tablosu)
       → kullanıcıya "profilini kontrol et" adımı (parsing hatası ~%15-25)

[Aşama 1 — Getirme (ucuz, tüm ilanlar üzerinde)]
  SQL hard filtre: yer, dil, min deneyim, maaş (embedding'den ÖNCE)
  → hibrit arama: vektör (cosine) + BM25, RRF fusion → top-50
  (BM25 katkısını golden set'te ölç — bazen zarar verir)

[Aşama 2 — Yeniden sıralama (orta maliyet, top-50 üzerinde)]
  Cohere Rerank (bedava tier) veya BGE-reranker-v2-m3 → top-10

[Aşama 3 — LLM-hakim (pahalı, top-10 üzerinde)]
  Gerçek uygunluk kararı + "neden uygun" açıklaması + kalite eşiği
  Azerice/Rusça metni doğrudan LLM'e ver (embedding'den iyi anlar)

[Aşama 4 — Bildirim]
  Sadece eşiği geçenler; batch; her eşleşmede açıklama + son başvuru tarihi
```

## Teknoloji kararları

| Katman | Karar | Neden |
|---|---|---|
| DB + vektör | **Supabase Postgres + pgvector** | Bedava, kartsız; metadata+vektör tek yerde; <10M vektörde standart. Günlük cron 7-gün pause'u da engeller |
| Embedding | **BGE-M3** (Cloudflare Workers AI bedava / self-host) | 100+ dil, düşük-kaynak dillerde stabil, dense+sparse, cross-lingual |
| Rerank | **Cohere Rerank bedava tier** (1000/ay) → taşarsa BGE-reranker self-host | Rerank = en yüksek etkili tek kalite artışı |
| LLM (ilanlar) | **Gemini Flash bedava** | İlan kamuya açık veri — eğitimde kullanılması sorun değil; kota cömert |
| LLM (CV'ler) | **Groq (Llama 3.3 70B) / Cohere / Cerebras** | 🔴 Bunlar veriyi eğitimde KULLANMAZ. CV kişisel veridir — bedava Gemini'ye ASLA gönderilmez (Google bedava tier'da prompt'larla eğitim yapıyor) |
| Çalıştırma | GitHub Actions cron (batch) + Supabase Edge Functions (webhook) | Bedava; bildirim işi real-time gerektirmez |
| Failover | Çoklu sağlayıcı (OpenRouter yedek) | Bedava kotalar habersiz değişiyor (Gemini Aralık 2025'te %50-80 kesti) |

## Dil stratejisi (Azerice = düşük-kaynak riski)

1. **Önce:** BGE-M3 multilingual, olduğu gibi (cross-lingual: AZ CV ↔ EN ilan çalışır)
2. JSON çıkarımları zaten İngilizce üretilir (ek maliyet yok, LLM zaten okuyor)
3. Golden set'te **nDCG@10 < 0.7** çıkarsa → translate-then-embed pivot ekle
4. LLM-hakim aşaması AZ/RU'yu doğrudan okur — son savunma hattı
5. Genel benchmark'lara güvenme: Azerice MTEB'de yok denecek kadar az; kendi setinde ölç

## Ölçüm (bunsuz her şey tahmin)

- **Golden set:** 50-100 elle etiketli (CV, ilan, uygun/uygun-değil) çifti — ilk iş
- **Offline:** nDCG@10, recall@k — her pipeline değişikliğinde
- **LLM-as-judge:** insan etiketlerine karşı doğrula (hedef %75-90 uyum); önce ikili
  geç/kal, sonra skor; açıklama zorunlu (uyumu artırır)
- **Online (asıl gerçek):** bildirim CTR, kaydetme/başvuru oranı, 3-7 gün retention
- **Feedback tablosu 1. günden:** tıkladı/kaydetti/başvurdu/reddetti → gelecekteki
  fine-tuning'in etiketli verisi = moat

## Yapmayacaklarımız (popüler ama bizim için yanlış)

- ❌ Tek başına vektör arama (reranker'sız) — hassasiyet zayıf
- ❌ Her eşleştirmede her şeyi LLM'e okutmak — pahalı, ölçeklenmez
- ❌ Graph DB / knowledge graph ana motor — gereksiz karmaşıklık
- ❌ Pinecone/Qdrant ile başlamak — pgvector yeter (100K+ ilanda tekrar bak)
- ❌ Başta fine-tuning / kendi model — etiketli veri yok; flywheel sonrası (Faz 2+)
- ❌ CV'yi bedava Gemini'ye göndermek — gizlilik ihlali
- ❌ Real-time eşleştirme — batch yeter ve çok daha ucuz

## Riskler ve önlemler

| Risk | Önlem |
|---|---|
| Scraping hukuki/ToS (hiQ $500K, Proxycurl kapandı) | Yavaş tarama, robots.txt, login arkasına geçme; uzun vadede site sahipleriyle ortaklık |
| Bildirim yorgunluğu (push kapatanların %52'si uygulamayı bırakıyor) | Kalite eşiği + batch + açıklama; az ama isabetli |
| CV parsing hatası (~%15-25 beceri hatası) | OCR fallback + kullanıcı onay adımı + parsing hata takibi |
| Çok-kaynak dublikasyon | Fingerprint/embedding ile dedup |
| Bedava tier kotaları değişken | Çoklu sağlayıcı failover; tek modele bağlanma |
| Azerbaycan KVK mevzuatı (sınır ötesi veri) | Opt-in şart; hukuki danışma gerekli (Faz 3 öncesi) |
| Rakip: "Expertini" tarzı semantik platformlar | Rekabet analizi yapılacak (ödev) |

## Geçiş eşikleri

- nDCG@10 < 0.7 → çeviri pivotu ekle
- İlan sayısı 100K+ → Qdrant değerlendir
- Bedava kota taşarsa → Gemini Flash paralı ($0.15/1M — hâlâ ucuz)
- Feedback verisi biriktiğinde → ConFit-tarzı fine-tuning (Faz 2+)
