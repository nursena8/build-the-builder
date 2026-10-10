# dev/gen_brief_a.py: brief'e bağlı sabitler (İŞ 3, Adım 5A)

Kaynak: sample builder'ın ürettiği `dev/gen_brief_a.py` (558 satır). Brief kural numaraları `briefs/brief-a.md`'den grep ile eşleştirildi (aşağıda "?" olanlar eşleştirilemedi: doğrulanmadı). "Sınıf": **B** = brief'ten (veya openapi'den) okunmalı, **G** = genel kalıp (brief'ten bağımsız, builder'da kalabilir).

## Sabitler

| Değer | Satır | Brief kuralı | Sınıf |
|---|---|---|---|
| Banka mock URL tabanı | 3 | (openapi/kit) | B (tool API'sinden) |
| Tool adları ve yolları: verify_identity, create_promise, schedule_callback, transfer_to_agent, close_call, get_account | 105-174, 436-440 | openapi | B |
| Kimlik alanları `date_of_birth`, `phone_last4` (enum) ve biçimleri (YYYY-MM-DD, 4 hane) | 108-109 | kural 11 civarı + openapi | B |
| Kimlik soru sırası: önce doğum tarihi, sonra telefon son 4 | 406 | brief kimlik bölümü (kural no ?) | B |
| Üç yanlış cevap sınırı, `wrong_answers_left == "0"` | 408, 419 | 12, 14 | B (sayı) / G (mekanizma) |
| `day_month_swapped` ipucu, yanlış sayılmaz | 64-65 | 13 | B (brief kuralı; openapi'de `hint`) |
| Callback saatleri 10:00-19:00 (araç açıklaması) | 130 | 6 | **B** |
| Callback penceresi metni: bugün `now`'dan sonra veya sonraki iş günü, 10:00-19:00 dahil | 240 | 6, 7 | **B** |
| Tatil listesi 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01 (kodda) | 184 | takvim bölümü (brief satır 53) | **B** |
| Aynı tatil listesi (prompt metni) | 218 | aynı | **B** |
| İş günü = Pzt-Cum (`weekday() < 5`) | 186, 229 | takvim bölümü | B (hidden'da farklı olabilir) |
| Erken bant deadline = 12. iş günü | 208 (`addbd(today, 12)`) | bant tablosu (brief satır 59) | **B** |
| Geç bant deadline = 7. iş günü | 209 (`addbd(today, 7)`) | bant tablosu (satır 60) | **B** |
| Bant eşikleri 1-7 / 8-45 ve ikna denemesi 1 / 2 | 214-215, 465 | bant tablosu | **B** |
| Persuasion attempt 1 tarihi = haftanın son iş günü (bugünse sonraki haftanınki) | 197-207, 216, 479 | 30 | B |
| Persuasion attempt 2 = floor tutarı, deadline tarihinde, yalnız geç bant | 480 | 30 | B |
| Floor: kredi kartında `minimum_payment`, kredilerde `instalment_amount` | 466 | tutar bölümü (24-27) | B (alan adları get_account şemasından) |
| "Next/this <weekday>" tanımı (gelecek haftanın o günü) | 238, 472 | 22 | B |
| Takvim tablosu üretimi (4 hafta, [past]/[today]/[not a business day]) | 219-237 | 22 civarı | G |
| Bir sonraki iş günü hesabı, `addbd` | 187-194, 210 | 20 | G |
| Kapanış eşlemesi (outcome, reason): callback, no_callback, wrong_number, deceased, unclear, failed, declined, support, restructuring, human, paid, dispute, hardship, refused, service_error, promise | 250-267 | outcome tablosu (brief satır 105-117) | **B** (adlar openapi + brief) |
| Outcome enum: promise, paid, transferred, no_promise, not_verified, not_reached | 166 | openapi | **B** |
| Reason'ın promise/paid için gönderilmemesi (`CLOSE_PRE`) | 95-102 | outcome tablosu | G (base-agent'ta da var) |
| Sabit cümle: açılış ("digital assistant ... call is recorded ... Am I speaking with {{title}} {{last_name}}?") | 349 | 1, 4 | **B** |
| Sabit cümle: "I am sorry for your loss." | 254 | 9 | B |
| Sabit cümle: app veya şube yönlendirmesi | 256 | 14 | B |
| Sabit cümle: "You will receive a text message confirming this promise." | 287 | 38 | B |
| Sabit cümle: ödemenin bir iş günü içinde görüneceği | 261 | 39 | B |
| Sabit cümle: "they can change it in the mobile app" | 491 | 36 | B |
| Sabit cümle: dolandırıcı sorusuna "customer service number" | 355, 542 | 43 | B |
| Sabit cümle: robot/AI sorusuna "Freya Bank's digital assistant" | 355, 541 | 4 | B |
| Transfer kuyrukları support / restructuring / general ve tetikleyiciler | 144-146 | 32, 41?, 42 + openapi enum | **B** |
| Kimlik öncesi yasak kelimeler: collections, debt, payment, late, ürün adı | 353 | 1, 5 | B |
| "recorded/saved/booked" yasağı ok:true gelmeden önce | 494, 545 | 37 | B (brief kuralı) |
| promise başarısızsa bir kez tekrar, iki başarısızlıktan sonra service_error | 83, 513 | 37 | B |
| Ürün başına bir promise | 123, 463 | 36 | B |
| Döngü korumaları: debt 80, security 25, third_party 10, confirm_name 10 tur | 362, 390, 414, 502 | (yok, sample builder seçimi) | G |
| Test değişkenleri (Daniel Reyes, c_test, now) | 557 | (PUB-01) | G (yalnız test) |
| Mock tool kullanım `maxRetries` 0 (yazan tool'lar), 2 (get_account) | 17, 434 | platform tuzağı | G |

## Node'lar ve görevleri

| Node | Tür | Görev |
|---|---|---|
| prepare | code | `now`'dan tarih/takvim/deadline bloğunu hesaplar, `date_facts` ve `deadline_early/late` değişkenlerine yazar (satır 177-248) |
| confirm_name | conversation | Sabit TTS açılış; kimlik teyidi, ikinci sorma, üçüncü kişi ayrımı, insan talebi (346-373) |
| third_party | conversation | Üçüncü kişiyle sınırlı konuşma, callback saati alma, `schedule_callback` (376-398) |
| security | conversation | Doğum tarihi, sonra telefon; `verify_identity`; 3 yanlışta close_failed (401-422) |
| load_account | api_request | `get_account` pre_action, `account_ok` değişkeni (425-456) |
| debt | conversation | Borç anlatımı, bant, tarih/tutar kuralları, ikna, itiraz/ödendi/plan/insan, onay ve `create_promise` (458-515) |
| close_* (16 adet) | code | Outcome, reason ve veda cümlesini değişkenlere hesaplar, hangup'a geçer (250-295, 517-518) |
| hangup | end_call | `farewell` cümlesini söyler, çağrıyı kapatır; workflow seviyesi close_call end_of_call'da çalışır (520-536) |

## Bant ve deadline seçimi: tam olarak nerede, nasıl

- **Hesap kodda:** satır 208-209: `de = addbd(today, 12)`, `dl = addbd(today, 7)`; satır 214-215'te iki deadline da `date_facts` metnine yazılır ("Deadline for days_late 1 to 7 (early band...)" ve "... 8 to 45 (late band...)"); satır 242-243'te `deadline_early`/`deadline_late` değişkenleri.
- **Seçim modelde:** `prepare` node'u `get_account`'tan ÖNCE çalışır, ürünün `days_late` değerini bilmez. Bandı seçmek `debt` prompt'una bırakılmış, satır 465: "BAND (read days_late of the product and pick the matching deadline; never mix them up)...". Model `get_account` sonucundan `days_late` okuyup iki deadline'dan birini seçer.
- **Hata:** PUB-04'te `days_late=14` (geç bant, 23 Ekim) iken model 3/3 koşuda erken bant deadline'ını (2 Kasım) seçti (bkz. EXPERIMENTS.md).
- **Kod tarafı çözüm yönü:** `get_account` sonrası, ürün başına `days_late`'ten bandı ve tek deadline'ı hesaplayan bir code node'u (load_account ile debt arasında) ve prompta yalnızca o ürünün deadline'ı ve deneme sayısı. Bu v1 tasarım önerisidir, uygulanmadı.
