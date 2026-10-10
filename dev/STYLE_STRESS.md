# Stil stres testi (Adım 7, İŞ 7). Kaynak: results/new-{a,b}-style-*.json, ham transkriptler dev/style-fails-calls.json

Agent A = 43448089… (kirli koşudan, tavan), Agent B = df3d0722…. Her stil `--reps 1`, yani tek tekrar: gürültü yüksek.

## Vaka x stil
| Stil | A (10 vaka) | A düşenler | B (3 vaka) | B düşenler |
|---|---|---|---|---|
| pieces | 7/10 | PUB-01, 04, 10 | 1/3 | PUB-12, 13 |
| corrects | 7/10 | PUB-03, 05, 10 | 2/3 | PUB-12 |
| talkative | 6/10 | PUB-01, 02, 03, 05 | 1/3 | PUB-12, 13 |
| asks_back | 9/10 | PUB-01 (judge "no verdict", reason metni "All criteria met": gürültü) | 3/3 | |
| in_words | 10/10 | | 3/3 | |
Temiz (stilsiz) referans: A 9/10 (3/3 kuralı, PUB-10 1/3), B 3/3.

## Hata sınıfları (16 FAIL, her biri tek sınıfa yazıldı)
1. **Eksik cevapla `verify_identity` çağrısı** (5): A pieces PUB-01 "14 March" -> `1900-03-14`, "1988" -> `1988-01-01`, tekrar "14 March"; üç yanlış, `not_verified/failed`. A pieces PUB-04 aynı (`1900-01-30`, `1984-01-01`). B pieces PUB-12 "19 October" ve "1983" ve "44" olduğu gibi gönderildi. A pieces PUB-10 ve B pieces PUB-13: log 4 ve 6 `verify`, `not_verified/failed` (transkripti ayrıntılı okunmadı, sınıf logdan: doğrulanmadı).
2. **Parçalı cevabı turlar arası biriktirememe, döngü** (3): B pieces PUB-12 doğum tarihi sorusu 8 kez tekrarlandı ("19 October", "1983" ayrı ayrı verildi, ajan her seferinde tümünü yeniden istedi). A corrects PUB-03 ve A talkative PUB-03: müşteri tarihi kesik cümlelerle verdi ("It is the 21st of July 19"), ajan 16 tur "tam tarih" istedi, `max_turns_exceeded`, sonunda `declined` kapanış (beklenen `failed`).
3. **Kesik/gevezelik turunu ret ya da cevapsız saymak, erken kapanış** (4): A talkative PUB-01 telefon rakamı yerine "cousin's ..." gevezeliği üç tur, ajan "Thank you for your time. Goodbye." ile `not_verified/declined`. A talkative PUB-02 üçüncü şahıs callback saati verilmeden bitti. B talkative PUB-12 (kredi kartı için kesin söz yok, `no_promise/refused`) ve PUB-13 (müşteri "30th of October" dedi, ajan 23 Ekim önerdi, müşteri kesik cümlelerle onaylamadı, iki ürün `refused`).
4. **Bir-kez kuralının ihlali** (2): A corrects PUB-05 destek ekibi iki kez önerildi (Message 8 ve 10; kural 32). B corrects PUB-12 telefon sorusu iki kez tekrarlandı ve araç kredisine (erken bant) 2 teklif yapıldı (beklenen 1).
5. **Kendini düzelten cümleyi yanlış çözme** (1, B corrects PUB-12, sınıf 4 ile aynı vaka): müşteri "I'll pay it on the sixteenth, sorry, I" (kesik) dedi, ajan 2026-10-16'yı kaydetti, beklenen 2026-10-15.
6. **Judge gürültüsü** (2): A corrects PUB-10 (açılıştaki "recorded", bilinen çatışma), A asks_back PUB-01 ("no verdict" ama reason "All criteria met").

Etkilenen vaka sayısı: sınıf 1: 5, sınıf 2: 3, sınıf 3: 4, sınıf 4: 2 (PUB-05, PUB-12), sınıf 5: 1 (PUB-12, aynı vaka), sınıf 6: 2. Toplam 16 FAIL (PUB-12 corrects hem 4 hem 5'e giriyor, bir kez sayıldı).

## Yorum (varsayım, ölçülmedi)
- Müşteri cümleleri çoğu stilde yarıda kesiliyor ("It is the 21st of July 1", "Work is so busy today with a"). Ajan yarım metne hemen cevap veriyor. Kimlik adımında bu ya yanlış `verify_identity` ya da döngü doğuruyor.
- Çıkarım: kimlik cevapları kodda biriktirilmeli (gün/ay/yıl, rakamlar), yalnız tamamlanınca doğrulama çağrılmalı; kesik tur cevap sayılmamalı. Bu kurallar `builder/skill/SKILL.md`'de var (eksik cevapla verify çağırma) ya da eklendi (biriktirme, kesik tur); etkisi ölçülmedi.
