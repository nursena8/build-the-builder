# dev/gen_phone_agents.py özeti ve brief'e bağlı sabitler (İŞ 3, Adım 5B)

658 satır. `python3 dev/gen_phone_agents.py` `out/brief-a.workflow.json` ve `out/brief-b.workflow.json` yazar. `openapi.json`'u okur (tool adları, yollar, alan adları, enum'lar tool tanımlarına oradan gelir: satır 10-48). B = A + `MULTI` bayrağı.

## Node'lar (A)

| Node | Tür | Görev | Tool'lar |
|---|---|---|---|
| prepare | code | `now`'dan takvim, deadline'lar (`dl_early`, `dl_late`), attempt-1 tarihi, `date_facts`, `callback_facts` (159-244) | - |
| opening | conversation | Sabit TTS açılış, kimlik teyidi; `line_status` extraction (confirmed/other_person/wrong_number/deceased/none); deterministik geçişler; 2. sorma sonrası unclear (559-572) | transfer_to_agent |
| third_party | conversation | Üçüncü kişi: callback saati alma, pencere kontrolü (573-581) | schedule_callback |
| security | conversation | TTS ilk soru; verify_identity; 3 yanlışta close_failed; reddetme (582-592) | verify_identity, transfer_to_agent |
| load_account | api_request | `get_account` pre_action, `products`/`account_ok` response_mapping (593-599) | get_account |
| account_facts | code | Ürün başına band, deadline, floor, geçerli tarihler, deneme sayısı ve teklifler (248-342) | - |
| debt | conversation | TTS `debt_statement`; hardship/ödendi/itiraz/plan/insan; tarih/tutar kuralları; onay ve create_promise (456-483, 619-621) | create_promise, transfer_to_agent (B: add_note) |
| close_* (14) + close_service_error_auto (A) | code | Outcome, reason, veda cümlesini hesaplar; `promise_guard`/`needs_promise` bayrakları (346-405) | - |
| hangup | end_call | `farewell` değişkenini söyler; workflow seviyesi close_call end_of_call (627-640) | - |

Geçişler: tool başarısına bağlı olanlar deterministik (`*_success_count > 0`, `all_verified`, `wrong_answers_left == 0`, `promise_id is_set`, `create_promise_failure_count > 1`, satır 550-551, 587-590, 604-607); sınıflama gerektirenler `matches_intent` tool-call geçişleri (`tc`, satır 74-76). Döngü koruması: opening 6, third_party 10, security 16, debt 60 tur (satır 572, 581, 592, 621).

## Bant ve deadline seçimi
- Deadline hesabı: `prepare` satır 194-195 (`early = addbd(today, 12)`, `late = addbd(today, 7)`), `dl_early`/`dl_late` değişkenleri (197-198).
- **Seçim kodda:** `account_facts` satır 296-304: `days = int(float(p.get('days_late')))`; `days <= 7` -> early, `dl_early`, 1 deneme; aksi halde late, `dl_late`, 2 deneme. Ürün başına geçerli promise tarihleri listesi (306-311), attempt-1 tarihi `a1p = a1 if a1 <= dl else dl` (305), teklif metinleri (313-323) `debt_facts` değişkenine yazılır; model yalnız o ürünün blokunu görür. Not: eşik `days <= 7` ve 45 üst sınırı brief'ten okunmuyor, koda gömülü. Üst sınır (45) kodda hiç yok.

## Outcome ve reason
`close_code` (346-385): her close_* node'u (outcome, reason, veda) sabit çifti `vars`'a yazar; `rec` (promise_id/create_promise sayacı) ile düzeltir: `promise_guard` kayıtlı promise varsa outcome'u `promise`'a çevirir ve text-message cümlesini ekler; `needs_promise` promise yoksa `no_promise/refused`; `transfer` queue'dan reason'ı türetir (`restructuring/general->human/support`, satır 366-367). Hangi close_* node'una gidileceği ise **modelin** `transition_to_close_*` çağrısı (A'da promise ve service_error hariç) veya deterministik koşul.

## Brief B: ürün imleci ve sayaç
**Kodda imleç/sayaç yok.** `account_facts` (MULTI=True) ürün başına bloklar üretir ve ürünleri sırayla anlatan `debt_statement` kurar (325-334); ürün sırası, ürün başına ikna sayacı, toplu geri okuma, tek onay, ürün başına `create_promise` ve `add_note` çağrıları `DEBT_TASK_B` prompt'unda modele bırakılmış (485-524). Kapanış önceliği ("ilk paid olmayan notun nedeni") de prompt'ta; `close_promise` B'de `tc` (modelin kararı), A gibi deterministik değil (610). Yani B çok-ürünlü akış 3 pratik vakada geçti ama mekanizma kod değil prompt: stabilite riski (3/3 ölçülmedi).

## A ile B farkı
`MULTI`: debt_statement ("Can you pay all of them today?"), DEBT_TASK_B, TOOL_NOTE, close_promise geçişi tc, `close_service_error_auto` yok (A'da `create_promise_failure_count > 1` ile otomatik), `max_turns`/tool listesi (601-621).

## Brief'e bağlı sabitler

| Değer | Satır | Brief kuralı | Sınıf |
|---|---|---|---|
| Tatiller 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01 | 161, 202, 250 (3 yerde kopya) | takvim bölümü | **B** |
| Pzt-Cum iş günü (`weekday() < 5`) | 163, 253 | takvim bölümü | B |
| Erken 12. / geç 7. iş günü | 194-195 | bant tablosu | **B** |
| Eşik `days <= 7`, geç bant 8-45 (45 kodda yok), deneme 1/2 | 297-304 | bant tablosu | **B** |
| Attempt 1 = haftanın son iş günü (bugünse sonraki hafta) | 179-193, 319 | 30 | B |
| Attempt 2 = floor, deadline'da, yalnız geç bant | 320-323 | 30 | B |
| Floor: kartta minimum_payment, kredide instalment_amount; tip adları credit_card/personal_loan/car_loan | 287-294 | tutar bölümü | B (alan adları şemadan) |
| Callback 10:00-19:00, dahil, bugün `now`'dan sonra / sonraki iş günü | 230-238 | 6, 7 | **B** |
| Sabit açılış cümlesi | 561 | 1, 4 | **B** |
| Sabit ilk güvenlik sorusu TTS | 584 | brief kimlik bölümü | B |
| Borç ifadesi metni ("collections team", "Can you make this payment today?") | 332-336 | 17 | B |
| Kimlik: doğum tarihi sonra telefon, alan adları, YYYY-MM-DD, 4 hane; `day_month_swapped` | 101, 447-454, 528-529 | 11-13 | B (alanlar openapi'den) |
| 3 yanlış, `wrong_answers_left == 0` | 589-590 | 12, 14 | B |
| Transfer kuyrukları restructuring/support/general ve tetikleyicileri | 366-367, 465-469, 531-532 | 32, 41?, 42 | **B** |
| Outcome/reason çiftleri ve veda cümleleri | 389-405, 542 | outcome tablosu | **B** |
| Sabit cümleler: "I am sorry for your loss", app/şube, "text message confirming this promise", "payments can take one business day", "customer service number" | 394, 396, 372, 399, 413 | 9, 14, 38, 39, 43 | B |
| Reason'ın promise/paid için gönderilmemesi (`PRE_CLOSE`) | 149-155 | outcome tablosu | G |
| "recorded yok ok:true öncesi", tek tekrar sonra service_error | 120-135, 482, 517 | 37 | B |
| B: add_note nedenleri refused/hardship/dispute/paid/service_error; kapanış önceliği | 520-524 | B kuralları | **B** |
| Tool eşlemesi, enum'lar | 10-48 (openapi'den) | openapi | **B** ama zaten dosyadan okunuyor (iyi) |
| Takvim tablosu üretimi, `addbd`, `nextbd`, hook kalıpları, `maxRetries 0/2`, `max_node_turns` | 164-176, 89-147, 33, 596 | platform tuzakları | G |
| Test değişkenleri (Daniel Reyes, c_test) | 639 | (PUB-01) | G (yalnız test) |
