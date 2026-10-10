# Build the Builder: Ana Başvuru Dokümanı

Bu yazı, şimdiye kadar konuştuklarımızın, kit dosyalarının (README, api.md, freya.py, run_cases.py, score.py, openapi.json, Brief A/B, base-agent.json, workflow-format.md, tools-and-code.md, public-test-set.json, SKILL.md, agent_builder.py) ve ekran görüntülerinin birleşimi. Sadece bu chate bakarak ilerleyebilmen için yazdım. Bilmediğim veya doğrulanmamış şeyleri "doğrulanmadı" diye işaretledim.

---

## 0. Özet

1. **Görev:** Bir tahsilat brief'ini okuyup Freya'da telefon agent'ı (workflow JSON) üreten bir program yazıyorsun. Agent'ı organizatörler simüle müşterilerle test ediyor.
2. **Skor:** Geçen vaka sayısı / toplam vaka. Kısmi puan yok.
3. **Final:** Pazar 20:00'de (İstanbul) hidden briefler açılıyor, 23:00'te teslim kapanıyor. 60 hidden vaka, her biri **üç koşunun üçünü de** geçmeli, farklı takvim günlerinde ve farklı konuşma tarzlarıyla.
4. **Sample builder** Brief A'da zaten 10/10 alabiliyor. Fark yaratacak şeyler üçü: tutarlılık (flaky olmamak), yeni brief'e genelleme ve hız.
5. **Ana strateji:** brief → spec (sabit şemalı ara temsil) → deterministik derleme → statik doğrulama → hedefli test → yama. Kuralları prompta değil, mümkün olan en sağlam mekanizmaya (kod, geçiş koşulu, sabit TTS, hook) koy.
6. **Maliyet:** Ekranlardan çıkan birim maliyet yaklaşık **$0.05 / çağrı dakikası** (platform ücreti ağırlıklı). Bir vaka-koşusu yaklaşık $0.10. $99.99 bakiye ile bol yetiyor, ama test merdivenini ucuzdan pahalıya kur.
7. **Platform sohbeti:** Öğrenmek ve bir transkripti incelemek için kullan. Skor ölçmek için kullanma.
8. **Teslim edilecekler:** Her final brief için `export_workflow` ile bir workflow JSON, builder kodu, bağımlılıklar, çalıştırma talimatı, her koşu için trace.

---

## 1. Görevin kesin tanımı

### 1.1 Kaynaklar arası karşılaştırma

| Konu | Kaynak | Not |
|---|---|---|
| Format | Hackathon sayfası | Online, solo veya en fazla 2 kişi |
| Domain | Hackathon sayfası | Debt collection, text konuşma |
| Practice | 13 vaka (Brief A: 10, Brief B: 3) | Ledger ile skorlanabilir |
| Hidden | 60 vaka | Pass rate |
| Zaman | Toplantı + mail | Hidden briefler Pazar 17:00 UTC (20:00 İstanbul), teslim 20:00 UTC (23:00 İstanbul). Teslim adımları hidden açılmadan önce mail ile gelecek |
| Builder girdisi | README | Brief dosyaları. Ek manuel adım yok |
| Teslim | README | Her brief için dışa aktarılmış phone agent dosyası, builder kodu, bağımlılıklar, trace |

Orijinal duyuru metni ("tek bir agent değil, sonraki agent'ı üretmeyi otomatikleştir") ile kit tam uyumlu. Tek fark: kit domaini tahsilat çağrısına sabitlemiş. Yani genel bir agent builder yerine "tahsilat brief → Freya workflow" derleyicisi yazıyorsun.

### 1.2 Skorun içeriği (README + score.py + run_cases.py)

Bir vaka sayılması için şunların hepsi gerekli:

1. **Ledger (banka kayıtları) doğru.** `score_ledger` şunları birebir karşılaştırıyor:
   - `(outcome, reason)` çifti. Reason olmayan outcome'larda ledger'daki reason **None** olmalı. Boş string `""` gönderirsen eşleşme bozulabilir. Base agent bu yüzden `close_call` için bir `pre_process_code` ile reason'ı siliyor.
   - Promise listesi: `(product_id, tutar (2 hane yuvarlama), tarih)`.
   - Not listesi: `(product_id, reason)`. `text` karşılaştırılmıyor.
   - Callback: `(tarih, saat)`, saat `HH:MM`.
   - Transfer: sadece `queue`.
   - Son tool çağrısı `close_call` olmalı.
   - Kimlik doğrulanmadan `get_account` veya `create_promise` çağrısı politika ihlali. Banka "identity not verified" hatası verirse ledger'a yazılır ve skor düşer.
   - `not_reached` sonuçlu vakada kimlik veya hesap tool'u kullanılırsa ihlal.
2. **Politika:** Konuşma brief içinde kaldı. Judge model (Gemini 3 Flash) transkripti vakaya özel kontrol listesiyle okuyor. Örnekler: "kimlik doğrulanmadan 'collections' kelimesi söylenmedi", "promise sonrası text-message cümlesi söylendi".
3. **Dürüstlük:** Tool başarısızken "kaydedildi" denmedi.

Skorda judge gürültüsü de var: Aynı agent bir koşuda geçip diğerinde kalabilir. Üç koşunun üçü şartı bunu daha da sert yapıyor.

### 1.3 Final ile practice arasındaki farklar

- Başka kimlik soruları. `run_cases.py` içinde `postcode`, `birth_year`, `company_number`, `founded_year` alanları hazırlanmış, yani hidden briefler büyük ihtimalle bunları kullanıyor.
- Başka limitler ve deadline'lar, başka outcome tablosu, başka takvim ve tatiller. İş günü tanımı da değişebilir (Pzt-Cum sabit değil).
- Biri temiz spec, diğeri ham banka malzemesi (mail, politika özeti, bir şeyi değiştiren memo, kod listesi).
- Tool API dosyası her brief için ayrı. 7 tool adı aynı, alan adları ve izinli değerler değişebilir.
- Vakalar 3 ürüne kadar çıkabilir.
- Müşteriler insan gibi konuşuyor: sayıyı iki parçada söylüyor, kendini düzeltiyor, konu dışına çıkıyor, soru soruyor, tutar ve tarihi sözle söylüyor.

### 1.4 Yasaklar

- Final briefin hiçbir kuralını, değerini veya adını builder koduna ya da prompt'una yazamazsın. Hata düzeltmek serbest, yeni brief'e özel veri eklemek yasak.
- Phone agent modeli sabit (`experimental-5`). `AGENT_LLM` değiştirilemez.
- Phone agent sadece bankanın tool API'sini çağırabilir. Workflow içi kod adımları ve hook'lar serbest.
- Agent'ı oluşturduktan sonra elle düzenlemek yasak.
- Builder koşusu brief başına en fazla 30 dakika, kendi testleri dahil.
- Aynı brief için builder'ı birden fazla koşturabilir, birinin ürettiği agent'ı o koşunun trace'iyle teslim edebilirsin.
- Sıralama eşitliğinde: geçen vakalardaki toplam promise tutarı, sonra daha kısa build süresi, sonra daha erken submission.

---

## 2. Kitin anatomisi

### 2.1 Dosyalar ve işlevleri

| Dosya | Ne yapar | Dikkat |
|---|---|---|
| `freya.py` | Freya API istemcisi (standart kütüphane) | `save_workflow`, `update_workflow`, `export_workflow`, `run_simulation`, `get_iteration`, `get_call` burada |
| `tools/run_cases.py` | Practice vakalarını bir agent'a karşı koşturup skorlar | Persona üretimi, simülasyon, ledger skoru, judge okuması, yavaşlık raporu |
| `tools/score.py` | Ledger skorlaması | Banka mock'una `x-team-key` ile bağlanır |
| `public-test-set.json` | 13 vaka | Kimlik, senaryo, beklenen ledger, judge kontrolleri |
| `examples/base-agent.json` | 2 node, 4 tool'lu örnek agent | 13 vakadan sadece 2'sini geçiyor |
| `examples/agent_builder.py` | Claude Agent SDK ile builder sarmalayıcısı | Trace'i `traces/*.jsonl`'e yazıyor |
| `.claude/skills/build-phone-agent/SKILL.md` | Builder'ın bilgisi | Minimal, aşağıda eleştirisi var |
| `docs/*.md` | Platform dokümanları | Tuzaklar tablosunda damıttım |
| `tools/openapi.json` | Banka tool API'si | Brief başına değişecek |

### 2.2 Betiklerin önemli davranışları

- **`save_workflow(slot, workflow)`**: İlk çağrıda oluşturur, sonra aynı workflow'u günceller ve yayınlar. `slot` etiketi `.freya-agents.json` içinde saklanır. Workspace limiti 200 workflow, bu yüzden her koşuda yeni oluşturma.
- **`update_workflow`**: PUT ile yeni sürüm kaydeder, ardından `agent_config` içindeki model `AGENT_LLM`'e eşit değilse düzeltip tekrar kaydeder, sonra son sürümü yayınlar. Yayınlamadan simülasyon eski sürümü koşturur.
- **`run_simulation`**: Başka bir simülasyon çalışıyorsa 30 sn bekleyip tekrar dener. Durum `completed`, `failed` veya `paused` olana kadar 10 sn'de bir sorar. Varsayılan `maxCallDurationSeconds` 420, eşzamanlılık 5 (`FREYA_SIM_CONCURRENCY`).
- **`run_cases.py`**: Her koşuda her vaka için `/v1/practice/sessions` ile taze bir müşteri oturumu açar. Personalar `.personas.json`'da önbelleklenir, metin değişirse yeniden oluşturulur. Seçenekler: `--brief A|B`, `--only ID1,ID2`, `--reps N`, `--style pieces|corrects|talkative|asks_back|in_words`, `--out`, `--rerun-if-slow`. Her koşu `results/log.jsonl`'e bir satır ekler. Her çağrı için en yavaş agent turunu ölçüp medyan 10 sn'yi aşarsa uyarır.
- **`agent_builder.py`**: Claude'u Agent SDK ile çalıştırır. Varsayılan model `claude-opus-5-5` (`BUILDER_MODEL` ile değişir), `max_turns=150`, Bash zaman aşımı 15-20 dk, arka plan görevleri kapalı. Bitişte tur sayısı, süre ve **maliyeti** yazdırır. Duvar saati sınırı yok.

### 2.3 Sample skill'in eksikleri

1. Test adımı `run_cases.py --brief A` ile practice vakalarına bağlı. Hidden briefte bu vakalar eski kurallara göre skorluyor, yani builder yanlış yöne düzeltir.
2. Brief'ten doğrudan workflow yazıyor. Spec çıkarma, kapsama denetimi ve statik doğrulama aşamaları yok.
3. "En fazla 3 kez test et" kuralı, test başına 3-11 dakikayla toplandığında 30 dakikalık sınırı aşabilir.
4. Her koşuda yaklaşık 20 bin tokenlık iki dokümanı baştan okutuyor. Bu hem pahalı hem yavaş.
5. En iyi sürümü saklama yok. Bir yama skoru düşürürse geri dönüş yok.
6. İlk node'un yalnızca "kimlik" olması, "başkası açtı", "yanlış numara", "vefat" gibi kimlik öncesi akışları modellemiyor.

---

## 3. Platform mühendisliği

### 3.1 Workflow modeli

- Workflow bir graf: **node** (adım), **transition** (geçiş), **variables** (tek global tablo, node kapsamı yok).
- Node türleri: `conversation` (diyalog, tool'lar burada), `api_request` (girişte HTTP çağrısı), `code` (girişte Python), `end_call` (kapat).
- Platform yanlış yerdeki alanları **sessizce siliyor**: `tools` yalnızca conversation node'larında, `pre_actions` yalnızca api_request ve code node'larında kalır.
- Her kullanıcı mesajından sonra **üç ayrı model çağrısı**: extraction (değişken çıkarır), routing (geçiş kararı, **diyalog prompt'unu görmez**), dialogue (cevap veya tool çağrısı).
- Deterministik koşullar (değişken kontrolü) model çağrısı gerektirmez.
- Phone agent modeli yavaş olabilir. Medyan tur 10 sn'yi aşarsa müşteri telefonu kapatıyor. Kısa node-yerel prompt'lar hem hızlı hem daha az kural atlar.

### 3.2 Tuzaklar tablosu

| # | Tuzak | Çözüm |
|---|---|---|
| 1 | `tools` conversation dışı node'da sessizce silinir | Çağrıyı api_request node'una `pre_actions` olarak koy veya conversation node'una tool yap |
| 2 | Boolean'a göre routing (`"true"` vs `"True"`) sessizce kırılır | String flag kullan veya iki yazımı da dene |
| 3 | `response_mapping` yanlış yerde yok sayılır | Tool için tool seviyesinde, `pre_actions` için node seviyesinde. Yollar `data.` ile başlar |
| 4 | `default` yerine `const` | `const` değeri bake etmez. Sabit değerler için `default` |
| 5 | `null` değerler şemayı bozar | İsteğe bağlı alanı çıkar veya `""` kullan |
| 6 | Extraction `min_confidence` varsayılanı 0.95 | Her değişkende elle ayarla (örn. 0.7) |
| 7 | Özel `extraction_prompt` girdi placeholder'ları olmadan hiçbir şey çıkarmaz | `{{extractor.speech}}`, `{{extractor.conversation.last-10}}` gibi placeholder'ları ekle |
| 8 | Tarihler `string` tipinde yıl tahmin edilir | `type: "date"` kullan |
| 9 | Kodda `{{` veya `}}` Python'u bozar | Kodda placeholder kullanma, değerleri `vars`'tan oku. İç içe dict'te `}}` olmasın |
| 10 | Kod exception atarsa sonuç tanımsız | Gövdeyi try/except ile sar ve her değişken için yedek değer yaz |
| 11 | Passthrough node'un `always` geçişi yoksa kilitlenir | Her passthrough node `always` ile bitsin |
| 12 | Tool sonrası agent susuyor veya negatif sonucu görmezden geliyor | Post-hook ile sonuca `what_to_do_next` satırı ekle ve prompta "tool sonrası konuş veya sonraki tool'u çağır" yaz |
| 13 | Tool'u model çağırmayabilir | Tool açıklamasına tetikleyici yaz ("CALL it every time…") |
| 14 | Yazan tool'larda `maxRetries` > 0 çift kayıt yapabilir | Yazan tool'larda `maxRetries: 0`, tekrar denemeyi agent mantığıyla yap |
| 15 | `{{var}}` çözülmezse prompt'ta sabit metin olarak kalır | Prompt'ta kullanılan her değişkeni önceki bir node'da koşulsuz ata |
| 16 | `context_variables` API'den kaydedilince sessizce kayboluyor | Kullanma, değerleri `{{değişken}}` ile prompta yaz |
| 17 | `max_node_turns` varsayılan 10, `max_turn_transition` yoksa etkisiz | Büyük değer ver ve hedef node tanımla |
| 18 | Güncelleme tek başına yayınlamaz | `save_workflow` yayınlar. Skor hiç değişmiyorsa `agentVersionNumber`'a bak |
| 19 | `agent_config`'i elle göndermek çağrıyı başlatamaz hale getirebilir | README: `agent_config`'i workflow'dan çıkar |
| 20 | `end_call` tool'undaki tetikleyici cümle ("Have a good day.") erken söylenirse çağrıyı bitirir | `end_call` node'u kullan (sessiz giriş, `message_mode: none`) |
| 21 | `/chat/message` rotası ilk code node'u atlayabilir | Code node'a bağlı akışı simülasyonla doğrula |
| 22 | Çözülmemiş tek-placeholder alan istekten düşer, karışık metin sabit placeholder gönderir | Karışık değerlerde placeholder kullanma |
| 23 | Çözülmemiş `{{var}}` parametresi varsa model çağrısı parametreyi kendisi doldurur | `close_call` parametrelerini koddan ata, yoksa model uydurabilir |

### 3.3 `close_call` ve base-agent JSON'u hakkında notlar

Yapıştırdığın JSON'dan ve ekran görüntülerinden çıkanlar:

- `close_call`, workflow seviyesinde `alwaysRunsAt: end_of_call` ile **her çağrı bittiğinde** çalışıyor, müşteri açıp kapatsa bile. Ekran görüntüsündeki 10 saniyelik çağrıda `close_call` otomatik çağrıldı. Parametreleri (`outcome`, `reason`) base agent'ta model dolduruyor, ve enum'da yalnızca 4 değer var (`paid` ve `transferred` yok). Builder enum'u `openapi.json`'dan okumalı.
- **Bu yüzden her manuel çağrı bir oturumu yakar:** banka `close_call`'dan sonra o `customer_id` için başka işlem kabul etmiyor. Workflow'un `test_variables` içindeki müşteri tek kullanımlık.
- `agent_config` (platformun doldurduğu) içinde `temperature: 0.7` ve `maxTokens: 1000` görünüyor. Sıcaklık 0.7, tutarsızlık kaynağı olabilir. README sadece modelin değiştirilmemesini söylüyor. Bu bir deney konusu ve organizatörlere sorulmalı (bölüm 11 ve 12). Dikkat: `agent_config`'i sıfırdan yazmak çağrıyı bozabilir, ancak platformun doldurduğunu GET ile alıp tek alanı değiştirmek `update_workflow`'un model için yaptığı şeyle aynı mantık.
- `llmConfig.systemPrompt` içinde "You are a helpful assistant…" gibi genel bir metin var. Workflow'un `system_prompt` alanı boş. Genel metnin diyaloğa nasıl karıştığı doğrulanmadı.
- Speech ayarları Türkçe (TTS Freya, STT tr). Değerlendirme metin tabanlı, bunlar sizi ilgilendirmiyor.

---

## 4. Brief A ve B analizi

### 4.1 Kural türleri ve en sağlam mekanizma

| Kural türü | Brief A/B örnekleri | Önerilen mekanizma |
|---|---|---|
| Açıklama kapısı (kimlik öncesi bilgi yok) | 1, 5, 10, 14, 16-17 | Sabit TTS açılış, kimlik node'una kadar `get_account` yok, geçiş koşulu |
| Sabit cümleler | 4 ("digital assistant"), 9 ("I am sorry for your loss."), 38 (text-message cümlesi), 47 (veda) | Sabit TTS veya hook'un `what_to_do_next` içinde verdiği cümle |
| Tarih mantığı | 6-7, 18-23, 30 | **Kod:** iş günü, deadline, "next Friday", takvim tablosu |
| Tutar mantığı | 24-27 | Kodla hesaplanan teklifler (tam tutar, floor) ve prompt |
| Sayaçlar | 12 (3 yanlış), 15, 30 (ikna denemesi), 45 | Hook veya kod değişkenleri |
| Tool sırası/dürüstlük | 34, 37, 46 | Hook'lar, `create_promise` başarısında cümle |
| Outcome tablosu | 46 ve tablo | Hook'ların tuttuğu değişkenlerden **kodla hesapla** |
| Serbest niyetler | 39-45 (ödedim, itiraz, plan, insan, dolandırıcı mı) | Global node'lar veya extraction enum'u + `equals` dalları |
| Ürün döngüsü (B) | 2-11 | Ürün imleci, ürün başına sayaç, toplu geri okuma, `create_promise` ürün başına bir kez |

### 4.2 Doğrulanmış tarih örnekleri (`now = 2026-10-14 Çarşamba 11:00`)

Bunlar ücretsiz yerel birim testi için referans (kod snippet'ini sahte `vars` ile yerelde çalıştır):

- **Geç bant (gün 8-45):** deadline = bugünden sonraki 7. iş günü = **23 Ekim** (PUB-04 beklenen).
- **Erken bant (gün 1-7):** deadline = bugünden sonraki 12. iş günü. 26 Ekim tatil atlanır → **2 Kasım**.
- PUB-07: müşteri "26'sı Pazartesi" der, tatil → sonraki iş günü **27 Ekim**.
- "Bu haftanın son iş günü" = **16 Ekim Cuma**. Bugün Cuma ise bir sonraki haftanın Cuma'sı.
- PUB-02: callback bugün veya sonraki iş günü, 10:00-19:00 dahil, `now`'dan sonra → **15 Ekim 11:00**.
- PUB-13: kart (erken) 30 Ekim kabul edilir, kredi (geç) kendi deadline'ı olan **23 Ekim**'e kaydedilir, geri okumada iki tarih de söylenir.
- PUB-06: floor 637.50 teklif edilir, "geri kalan gecikmede kalır" denir, Cuma 16 Ekim.
- "Next Friday" kuralı (22): bir sonraki takvim haftasındaki Cuma. Cuma günü "next Friday" bir sonraki haftanın Cuma'sı.

### 4.3 Vaka profilleri (practice)

| Vaka | Test ettiği |
|---|---|
| PUB-01 | Mutlu yol, tam tutar bugün |
| PUB-02 | Üçüncü kişi, callback |
| PUB-03 | 3 yanlış cevap, tutar sızdırmama, app/şube yönlendirmesi |
| PUB-04 | Deadline sonrası tarih, "robot musun" |
| PUB-05 | Zorluk (hardship), sempati, indirim yok, destek teklifi bir kez |
| PUB-06 | Floor teklifi, "ne kadar ödeyebilirsin" asla sorulmaz |
| PUB-07 | Belirsiz dönem, tatil günü |
| PUB-08 | "Zaten ödedim" → `paid` |
| PUB-09 | Yeniden yapılandırma → transfer |
| PUB-10 | `create_promise` ilk çağrıda 500, tekrar deneme, "kaydedildi" demeden önce ok:true |
| PUB-11 | 3 ürün, tek tarih, tek onay, 3 promise |
| PUB-12 | Bir ürüne söz, ikisini reddetme, ürün başına ikna denemeleri, not |
| PUB-13 | Tek tarih, farklı deadline'lar |

### 4.4 Brief B için sıralı akış

Ürünleri `get_account` sırasıyla ele al: önce hepsini say, sonra "hepsini bugün ödeyebilir misin?", sonra ürün ürün git. İkna denemeleri ürün başına. Tüm promise'ları tek seferde geri oku, tek onay al, sonra ürün başına bir `create_promise`. Promise verilmeyen ürüne `add_note` (`refused`, `hardship`, `dispute`, `paid`, `service_error`). Transferlerde hiç not yok. Kapanışta en az bir promise varsa `promise`; hiç yoksa ve hepsi `paid` ise `paid`, değilse `no_promise` ile ilk `paid` olmayan notun nedeni. Ürün id'lerini modele uydurtma, kodla doldur ("unknown product_id" hatası README'de uyarılıyor).

---

## 5. Hidden brief'e hazırlık ve genelleme

### 5.1 Spec şemasında olması gerekenler

Brief'ten çıkarılan sabit şemalı ara temsil şu alanları taşımalı (alanlar brief'e göre boş olabilir):

- **Çağrı değişkenleri:** hangi değişkenler geliyor, hitap biçimi.
- **Açılış:** zorunlu ilk cümle öğeleri (kayıt bilgisi, kimlik beyanı), yasak kelimeler (kimlik öncesi).
- **Kimlik:** soru listesi (alan adı, sorulma sırası, cevap formatı ve dönüştürme kuralı), yanlış cevap limiti, "ayın adını söyle" gibi özel tekrar kuralları, reddetme akışı, başarısızlık sonucu.
- **Üçüncü taraf:** neyin söylenip neyin söylenmeyeceği, callback penceresi (gün, saat aralığı, dahil/hariç), yanlış numara, vefat cümlesi.
- **Takvim:** iş günü tanımı, tatil listesi, "next/this weekday" kuralları.
- **Bantlar:** eşik, deadline (iş günü sayısı), ikna denemesi sayısı ve içeriği.
- **Tutarlar:** floor kuralı (ürün tipine göre), kabul aralığı, teklif sırası, yasaklar ("ne kadar ödeyebilirsin" sorma).
- **Söz alma:** geri okuma, onay, kayıt, başarısızlıkta tekrar, sonrasında söylenecek cümle.
- **Diğer niyetler:** ödedim, itiraz, plan talebi, insan talebi, dolandırıcı mı, bilinmeyen soru, isteksizlik sayacı.
- **Çok ürün:** sıra, toplu onay, notlar, kapanış önceliği.
- **Outcome tablosu:** outcome, reason, hangi kural tetikler.
- **Veda ve ton kuralları.**
- **Tool eşlemesi:** hangi tool hangi alanları kabul ediyor (openapi'den), enum'lar.

### 5.2 Ham malzeme (mail, memo, politika özeti, kod listesi)

Builder şu sırayla davranmalı:

1. Her kaynaktaki kuralları kaynak bilgisiyle çıkar.
2. Çakışmalarda öncelik: sonraki memo önceki politikayı ezer, kod listeleri anlam kazandırır.
3. Çözülemeyen belirsizlikleri işaretle ve en güvenli yorumu seç.
4. **Kapsama denetimi:** Kaynaktaki hangi kural spec'te karşılıksız diye ayrı bir geçişte sor.

### 5.3 Brief'e özel veri koymadan genel kalıp kütüphanesi

Builder'a koyabileceğin genel (brief'ten bağımsız) bilgiler:

- Platform kalıpları: kimlik kapısı, kodla hesaplanan `date_facts` bloğu, tool sonrası `what_to_do_next`, outcome'u hook değişkenlerinden hesaplayan `close_call`, ürün imleci döngüsü.
- Sayı ve tarih normalleştiriciler (rakam kelimeleri → rakam, "oh" → 0, kelimeyle söylenen tarihler → ISO). Bunlar brief'e özgü değil, "insan gibi konuşan müşteri" için genel.
- Genel domain bilgisi (tahsilat çağrılarının tipik aşamaları: açılış, kimlik, açıklama, pazarlık, onay, kayıt, kapanış).

Yasak olan: Brief A/B'nin sayılarını, tatillerini, outcome adlarını koda gömmek. Test: Hidden brief'te farklı olacak her değer spec'ten gelmeli.

---

## 6. Builder mimarisi

### 6.1 Aşamalar

1. **Girdi okuma:** Brief dosyaları (bir veya birkaç, farklı türde olabilir) ve `openapi.json`. Brittle parser yerine LLM okumasını tercih et. Çökme düzeltmesi hidden sonrası serbest, yeni veri eklemek değil.
2. **Spec çıkarma (LLM):** Bölüm 5.1 şemasında bir JSON dosyası.
3. **Kapsama denetimi (ayrı LLM geçişi):** Kaynakta karşılığı olmayan kuralları listele, eksikleri spec'e ekle.
4. **Derleme (deterministik şablon + LLM prompt parçaları):** Spec'ten node, geçiş, kod, hook, tool tanımlarını üret. Kural → mekanizma eşlemesini tablo olarak sakla ve her kuralın bir yere atanıp atanmadığını kodla kontrol et.
5. **Statik doğrulama (senin yazacağın deterministik script, LLM değil):** `null` var mı, `tools` doğru node türünde mi, her passthrough'un `always` geçişi var mı, kodda `{{` var mı, boolean routing var mı, tool alanları ve enum'lar openapi ile birebir mi, tüm yollar bir `end_call` node'una ulaşıyor mu, `close_call` hesaplanmış outcome'a mı bağlı.
6. **Dry-run + kaydet + yayınla** (`validate_workflow`, `save_workflow`).
7. **Hızlı testler:** chat API ile kural bazlı probe'lar.
8. **Simülasyon:** Kendi ürettiği personalarla.
9. **Teşhis ve yama:** Başarısız vakayı bir kurala bağla, o kuralın mekanizmasını düzelt (prompt'a tekrar yazmak yerine).
10. **En iyi sürümü sakla:** Her turun skorunu ve dosyasını `out/` altında tut, sonda en iyisini yayınla.
11. **Dışa aktar:** `export_workflow`.

### 6.2 Test üretimi (kritik açık)

Hidden briefte practice müşteriler ve ledger muhtemelen yok. Builder kendi personalarını spec'ten üretmeli (kural başına bir persona, mutlu yol, tarz varyantları), judge için başarı kriterlerini spec'ten yazmalı. **Açık soru:** Mock banka yeni brief için test oturumu (müşteri + hesap verisi) üretmeyi destekliyor mu? `run_cases.py`'nin kullandığı `/v1/practice/sessions` sadece bilinen vaka id'lerini tanıyor. Destek yoksa builder tool çağrılarını gerçekçi veriyle test edemez. Bunu organizatörlere sor (bölüm 12).

### 6.3 Deterministik tool çağrısı alternatifi (deney)

Kimlik ve söz kaydı adımlarını iki yoldan kurmak mümkün:

- **Model-güdümlü tool:** Conversation node'unda tool var, model çağırır. Risk: eksik rakamla çağırıp yanlış cevap hakkı yakmak (`pieces` tarzı), format hatası.
- **Extraction → api_request node'u:** Extraction doğrulama deseniyle (`^[0-9]{4}$`) değeri çıkarır, değişken set olunca bir passthrough api_request node'u değeri bake ederek çağrıyı **motor** yapar, model sadece konuşur. Risk: extraction'ın güvenilirliği, ek gecikme.

İki yolu kimlik ve söz kaydı adımlarında ölçerek karşılaştır (bölüm 11, E4).

### 6.4 Zaman bütçesi (30 dakika)

Bir 10'luk simülasyon 3-11 dakika sürüyor. Gerçekçi dağılım: ilk 6-10 dk spec çıkarma ve denetim, sonraki 4-6 dk derleme, doğrulama ve kaydetme, 10-11 dk bir tam simülasyon, geri kalan teşhis ve yama. Kural:

- Başlangıç saatini kaydet.
- Kalan süre bir simülasyonun maksimum süresinden azsa yeni test turu başlatma, en iyi sürümü yayınla ve bitir.
- Agent SDK sarmalayıcısına **duvar saati zaman aşımı** ekle (örnek wrapper'da yok).

### 6.5 Claude Agent SDK ve skill düzeni

- Builder'ın bilgisi `.claude/skills/` altında. Birkaç ayrı skill: (a) spec çıkarma ve kapsama denetimi, (b) platform kalıpları (dokümanların damıtılmış hali, brief'e özel değer yok), (c) test ve teşhis (persona üretimi, kural-bazlı hata sınıflandırması, öncelik sırası: uyum ihlali > ledger/outcome > konuşma kalitesi).
- Dokümanları her koşuda baştan okutmak yerine damıtılmış kalıpları skill'e koy. Bu hem giriş token maliyetini hem süreyi düşürür.
- `setting_sources=["project"]` kullanıldığı için çalışma klasörü ayarları (ve büyük olasılıkla `CLAUDE.md`) builder koşusuna yüklenir (doğrulanmadı, SDK dokümanından kontrol et). Geliştirme talimatlarını teslim edilecek `builder/` klasöründen ayrı bir yerde tut.
- Model seçimi: `BUILDER_MODEL`. Geliştirmede daha ucuz bir model (örn. `claude-sonnet-5-5`), final için sonuçlara bakarak karar ver. Daha üst katman modeller denenebilir ama maliyet ve kısıtlamalarını önce küçük bir testle gör.

### 6.6 Trace

README: koşunun başlangıç ve bitiş zamanı, her model çağrısı (model + tek satır amaç), Freya'da oluşturulanlar, kendi agent'ı üzerinde koştuğu testler. Sarmalayıcı mesajları zaten `traces/*.jsonl`'e yazıyor. Builder içinde ayrı bir LLM çağrısı (örn. doğrudan Anthropic SDK ile spec çıkarma) yaparsan aynı trace'e kendin logla. Teslimden önce trace'te ve repoda API anahtarlarını temizle.

### 6.7 Çalışma zamanında kendini yeniden yazan builder

Konuştuğumuz gibi: runtime'da kendi kodunu değiştiren bir builder yapma. Final benchmark builder'a geri bildirim vermiyor, doğrulanamaz karmaşıklık yaratır. Meta-öğrenmeyi **offline** yap: deney günlüğü, hangi kalıp hangi hata kategorisini düzeltti, builder konfigürasyonu ve skill'leri bu kayıtlara göre elle güncelle.

---

## 7. API kullanım rehberi

### 7.1 Temel ayarlar

- Taban URL: `https://staging-app.freyavoice.ai`. Başlık: `Authorization: Bearer fak_...`. **Tarayıcı benzeri User-Agent şart** (yoksa HTML sayfası ve `error code: 1010`). `freya.py` bunu ayarlıyor.
- Yanıt zarfı: `data.result` içinde. Workflow ve call rotaları tekil (`/workflow`, `/call`), persona ve simülasyon rotaları çoğul.
- Liste rotaları `workspaceId` sorgu parametresi ister. Birden fazla workspace görüyorsan `FREYA_WORKSPACE_ID` ayarla. Ekran görüntülerinde senin workspace id'n `a12f372c-bc29-486c-85e3-87dda54db62c`.
- Env: `FREYA_API_KEY`, `FREYA_BANK_TEAM_KEY` (16+ karakter, **her seferinde aynı**), isteğe bağlı `FREYA_WORKSPACE_ID`, `FREYA_SIM_CONCURRENCY`. `FREYA_AGENT_PROVIDER/MODEL` organizatörlere ait, dokunma.
- `env.sh` dosyasını ve anahtarları repoya, trace'e veya bu chate koyma.

### 7.2 Rota tablosu

| Amaç | Çağrı | Maliyet | Not |
|---|---|---|---|
| Workflow doğrulama (kaydetmeden) | `POST /api/v2/workflow?dryRun=true` | Çağrı yok | Şema doğrular, alanları sessizce siler. Sonucu geri okuyup bak |
| Oluştur | `POST /api/v2/workflow` | Çağrı yok | `workflow.id` ve `workflow.agentId` döner |
| Güncelle | `PUT /api/v2/workflow/{id}` | Çağrı yok | Gövde tüm tanımı değiştirir, eksik anahtar silinir. **Yayınlamaz** |
| Sürümler/yayın | `GET /api/v2/versions/workflow/{id}` ve `POST .../publish` | Çağrı yok | `save_workflow` ikisini de yapar |
| Oku | `GET /api/v2/workflow/{id}?workspaceId=...` | Çağrı yok | Platformun doldurduğunu görürsün |
| Persona oluştur | `POST /api/v2/personas` | Muhtemelen ücretsiz | `successCriteria` judge'a gider |
| Simülasyon | `POST /api/v2/simulations`, sonra `GET .../{id}` | **Çağrı dakikası** | Üç agent override'ını ver |
| Koşular | `GET .../iterations`, `.../iterations/{iterationId}` | Çağrı yok | 30 koşu varsayılan, `limit` 100'e kadar, sayfalama |
| Transkript | `GET /api/v2/call/{callId}` | Çağrı yok | `messages` içinde `route_evaluated`, `variable_table`, tool çağrı argümanları |
| Tek tur sohbet | `POST /api/v2/chat/message` ve `POST /api/v2/chat/end` | Çağrı dakikası (muhtemelen daha az) | Aynı `callId` ile devam |

### 7.3 Teşhis için `route_evaluated`

Geçişlerin neden tetiklenmediğini görmenin en hızlı yolu: her dalın değişkeni, operand'ı ve sonucu görünür. Bir değişkenin gelip gelmediğini `variable_table` ile kontrol et. Prompt'ta adını görmek kanıt değildir.

### 7.4 Banka mock'u

- Pratik oturum: `/v1/practice/sessions` (vaka id'siyle) taze müşteri değişkenleri döner. Kitteki `score.http` yardımcısı bunu çağırıyor.
- Ledger: `/v1/practice/ledger/<customer_id>` çağrıların tam dökümü. **Platform kredisi harcamaz.**
- 7 tool: `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call`. Hata davranışı: `ok:false` yanıtı eylemin gerçekleşmediğini söyler, 500 hiçbir şey kaydetmez ve tekrar denenebilir. Servis kuralları uygulamıyor: tatilde veya deadline sonrasında promise'ı sorunsuz kaydeder, kurala uymak agent'ın işi.
- `verify_identity`: yanlış cevap hakkı toplam 3. Okunamayan tarih `ok:false` döner ve yanlış sayılmaz. Gün-ay yer değiştirmişse `hint: "day_month_swapped"` döner. Geçerli iki cevaptan sonra `all_verified`.

### 7.5 Sık hatalar

| Belirti | Neden | Çözüm |
|---|---|---|
| `error code: 1010` HTML | User-Agent yok | `freya.py` kullan |
| `Workspace plan limit reached` | Çok fazla workflow | Yerinde güncelle |
| Skor hiç değişmiyor | Güncelleme yayınlanmadı | `save_workflow`, `agentVersionNumber` kontrol |
| Simülasyon "running"da takılı, çağrı başlamıyor | Workflow çağrı başlatamıyor | Tek chat turu dene, `agent_config`'i çıkar |
| `unknown product_id` | Model id uydurdu | `get_account` sonucundan ver veya kodla doldur |
| 504 / 500 chat | Uzun tur veya workflow başlayamıyor | Tekrar dene veya workflow'u kontrol et |
| `another simulation is running` | Workspace başına tek simülasyon | `run_simulation` bekler, ikinciyi başlatma |

---

## 8. Platform sohbeti, API chat ve simülasyon: ne zaman hangisi

| Durum | Araç | Maliyet | Notlar |
|---|---|---|---|
| Platformun nasıl çalıştığını öğrenmek (routing, değişken tablosu) | Workflow sayfasında **Text Agent** + Call Logs'ta **Logs** ve **Variables** sekmeleri | ~$0.05/dk | İlk birkaç saat için. Transition'ların "Route evaluated" olaylarını görürsün |
| Bir kuralın çalışıp çalışmadığını hızlıca denemek | API `chat/message` (taze oturum ile) | Düşük | Tek tur veya kısa konuşma |
| Ses (**Call Agent**) | Kullanma | Daha pahalı (TTS+STT) | Değerlendirme metin tabanlı |
| Skor ölçmek | `run_cases.py` | ~$0.10/vaka | Tek yeşil koşu kanıt değil |
| Başarısız vakanın nedeni | `get_call` veya platformdaki Logs/Variables | Çağrı yok | Transkript, tool argümanları, `route_evaluated`, `variable_table` |
| Final | Sadece builder, UI'a dokunma | | UI'ı yalnızca izlemek için kullan |

### 8.1 Manuel test prosedürü (önemli)

`close_call` her çağrı sonunda çalışıp oturumu mühürlediği için workflow'un `test_variables`'ındaki müşteri **tek kullanımlık**. Her manuel denemeden önce taze bir oturum al (`/v1/practice/sessions`, örn. `PUB-06`), dönen değişkenleri chat API'sinin `customerVariables` alanına veya platformdaki çağrı değişkenlerine koy. Konuşma bitince ledger'ı `/v1/practice/ledger/<customer_id>` ile oku: agent ne kaydetti, ne çağırdı hemen görürsün. Ekran görüntüsündeki 10 saniyelik çağrı da bir oturumu yaktı.

### 8.2 Elle düzenleme ve builder

Geliştirme sırasında platformda elle denemek serbest ve öğretici ("önce kendin yap"). Ama elle bulduğun her çözümü builder'a kodla. Final koşusunda hiçbir elle düzenleme yok.

---

## 9. Maliyet ve kredi yönetimi

### 9.1 Ekranlardan ölçülenler

- 10 saniyelik bir web çağrısı **$0.0105**: platform ücreti $0.0083 (%79), STT $0.0017, TTS $0.0004, analiz $0.0001, workflow $0.
- Demo çağrıları: 1:43 → $0.0866, 1:13 → $0.0625, 0:28 → $0.0234, 0:16 → $0.0137. Hepsi yaklaşık **$0.05 / çağrı dakikası**. Maliyet süreye orantılı, takılıp uzayan çağrılar pahalı.
- Senin ölçtüğün ~$0.1'lik "arama" yaklaşık 2 dakikalık bir çağrıya karşılık geliyor, tutarlı.
- Bakiye ekranlarda **$99.99**, 5 eşzamanlı çağrı kanalı.

### 9.2 Tahmini birimler (doğrula)

- Bir vaka-koşusu: ~1-3 dk → **~$0.05-0.15**. Planlamada $0.10 kullan.
- 13 vakalık tam koşu: ~$1.3. `--reps 3`: ~$4.
- Bakiye yaklaşık 70 tam koşuya yeter. İlk tam koşuyu yaptıktan sonra bakiye farkına bak ve bu birimi gerçek değerle değiştir.
- Chat API ve simülasyon metin modunda STT/TTS ücreti olmaması muhtemel ama platform ücreti süreyle ölçekleniyor olabilir (doğrulanmadı).

### 9.3 Bütçe planı (yaklaşık $100)

| Kalem | Tahmini |
|---|---|
| Baseline ve keşif | ~$15 |
| Geliştirme iterasyonları (hedefli koşular) | ~$35 |
| `--reps 3` ve tarz varyantları ile stres testleri | ~$20 |
| Final prova ve final builder koşuları (6 koşu × ~3 test turu × 10 vaka) | ~$20 |
| Yedek | ~$10 |

### 9.4 Test merdiveni (ucuzdan pahalıya)

1. **Yerel statik doğrulama** (ücretsiz): doğrulayıcı script.
2. **Yerel birim testleri** (ücretsiz): kod snippet'lerini sahte `vars` ile çalıştır. Tarih fonksiyonu için bölüm 4.2'deki örnekler hazır test seti.
3. **Dry-run** (çağrı yok).
4. **Chat probe'ları** (düşük): belirli bir kural.
5. **`run_cases.py --only ID1,ID2`**: değişikliğin etkilediği vakalar.
6. **Tam 13 vaka, tek tekrar**: bir özellik bitince.
7. **`--reps 3` ve tarz varyantları**: sadece sürüm adayları için.

### 9.5 Tasarruf kuralları

- Küçük değişiklik için 13 vakayı koşturma, `--only` kullan.
- Çalışan bir simülasyon varken ikinciyi başlatma (kuyruğa girer, boş yere beklersin).
- Sesli çağrı yapma.
- Bakiyeyi her aşamadan önce ve sonra not et.
- Takılan çağrılar için `max_node_turns` ve `max_turn_transition` tanımla. İstersen geliştirme sırasında simülasyon süresi limitini (varsayılan 420 sn) kendi araçlarında düşür.
- `run_cases.py`'nin uyardığı yavaşlık durumunda (medyan > 10 sn) skoru güvenme, `--rerun-if-slow` kullan.

### 9.6 Anthropic tarafı maliyeti

Builder koşuları Claude'u çağırıyor (150 tura kadar). Sarmalayıcı bitişte `$` olarak maliyeti yazdırıyor, ilk koşuda ölç. Birkaç Claude Code oturumunu paralel açıp yoğun model kullanırsan Cumartesi-Pazar boyunca kotayı tüketip Pazar akşamı final koşularına kota kalmaması riskin var. Çözüm: final builder koşuları için ayrı bir pay-as-you-go API anahtarı kullan veya kotayı koru, ve Pazar öğleden sonra yoğun denemeleri azalt.

---

## 10. Zaman çizelgesi

Şu an Cumartesi öğleden sonra, Pazar 20:00'ye (hidden brieflerin açılışı) yaklaşık 28 saat var.

**Aşama 0: Cumartesi 16:00-17:00, ortam ve baseline**
- `env.sh` hazırla (API anahtarı, team key, workspace id).
- Base agent'ı kaydet ve `run_cases.py --brief A` ile koştur (yaklaşık 2/13 beklenir). Maliyeti, süreyi ve bakiye farkını not et.
- Sample builder'ı Brief A ve A+B için koştur. Skor, süre, Anthropic maliyeti, trace.
- Bir manuel chat denemesi yap (taze oturum + ledger okuma).

**Aşama 1: 17:00-19:00, tutarsızlık araştırması**
- Sample builder'ın çıktısı ile `--reps 3` ve iki tarz koş. Başarısızlıkları şu kategorilere ayır: judge gürültüsü, tool sırası, tarih mantığı, tool sonrası sessizlik, kimlik hakkı yanma, outcome yanlış.
- Organizatörlere sorular gönder (bölüm 12).
- Mimariyi kesinleştir.

**Aşama 2: Akşam-gece, çekirdek**
- Spec şemasını dondur. Derleyici, statik doğrulayıcı, tarih kodu ve yerel testleri yaz. Geceyi uyku ile böl, yorgunken yazılan kodun maliyeti yüksek.

**Aşama 3: Pazar 09:00-13:00, entegrasyon**
- Brief A ve B ile uçtan uca. Mutant briefler. Ham malzeme varyantı. Zaman bütçesi ve zaman aşımı. Trace.

**Aşama 4: 13:00-17:00, sağlamlaştırma**
- `--reps 3` ve tüm tarz varyantları. Yeni özellik yok, sadece hata düzeltme.

**Aşama 5: 17:00-19:30, dondurma ve prova**
- Builder'ı dondur (git etiketi). Gerçek final gibi baştan prova: A ve B üzerinde sıfırdan koş, 30 dakikayı geçmediğini, trace'in düzgün olduğunu, `export_workflow` dosyalarının geldiğini doğrula. Bağımlılık dosyası ve çalıştırma talimatı (README, `env.example`, gerekli Python sürümü) hazır olsun. Repoda ve trace'te anahtar olmadığını kontrol et.

**Aşama 6: 20:00-23:00, final**
- Brief'leri sadece formatı görmek için aç, elle düzenleme yok. Builder'ı sırayla koştur (aynı workspace'te paralel koşma, simülasyonlar kuyruğa girer ve her koşunun 30 dakikası bozulur). Süre izin veriyorsa her brief için ikinci bir koşu yap ve kendi ölçümüne göre daha iyi olanı seç. Hidden brief sonrası yalnızca çökme düzeltmesi yap, brief'e özel veri ekleme. Teslim adımları mail ile gelecek, 22:30'a kadar bitir.

---

## 11. Deney listesi

| # | Hipotez | Nasıl | Ölçüt |
|---|---|---|---|
| E1 | Sample builder çıktısı practice'te ne kadar tutarlı? | `--reps 3`, 2 tarz | Vaka bazında 3/3 oranı |
| E2 | Tarih ve takvim kodda hesaplanınca tarih hataları kayboluyor mu | Kodlu `date_facts` ile PUB-04, 06, 07, 13 | 3/3 geçiş |
| E3 | `what_to_do_next` hook'u tool sonrası sessizliği çözüyor mu | PUB-10 ve ürün akışları | Susan çağrı sayısı |
| E4 | Extraction → api_request mi, model-güdümlü tool mu daha tutarlı | Kimlik ve söz kaydı adımlarında A/B | 3/3 oranı, gecikme |
| E5 | Outcome'u kodla hesaplamak ledger hatalarını azaltıyor mu | `close_call` parametreleri baked vs model | Outcome/reason uyuşmazlığı |
| E6 | Sıcaklık düşürmek tutarlılığı artırıyor mu (organizatör izni gerekli) | `agent_config` içinde yalnızca `temperature` | 3/3 oranı |
| E7 | Node-yerel kısa prompt vs tek büyük prompt | Aynı kurallar iki yapıda | Atlanan kural, medyan tur süresi |
| E8 | Ham malzemede çakışma çözümü çalışıyor mu | Mutant ham malzeme briefleri | Spec doğruluğu (elle kontrol) |
| E9 | Persona üretimi kural başına yeterli mi | Builder'ın ürettiği persona seti ile transkript okuma | Yakalanan hata sayısı |
| E10 | Builder'ın toplam süresi 30 dk altında mı | Prova koşuları | Süre dağılımı |

Her deneyi `EXPERIMENTS.md`'ye yaz: değişiklik, hipotez, sonuç, maliyet.

---

## 12. Organizatörlere sorulacaklar (öncelik sırasıyla)

1. **Hidden brief için test oturumu:** Builder kendi agent'ını denerken tool çağrılarının çalışması için mock banka yeni brief'e uygun sahte müşteri ve hesap verisi üretebilecek mi (`/v1/practice/sessions` benzeri bir endpoint), yoksa builder sadece konuşma akışını mı test edebilecek? Final briefle birlikte practice müşteri verilecek mi?
2. **Temperature ve `agent_config`:** Builder `agent_config` içindeki `temperature` veya `maxTokens` gibi alanları ayarlayabilir mi, yoksa yalnızca modelin değiştirilmemesi mi kuralı?
3. **Paralel koşu:** Aynı brief için iki builder koşusunu ayrı workspace veya anahtarla paralel koşturmak serbest mi? Yoksa tek workspace, tek simülasyon sınırı yüzünden sıralı mı gitmeliyiz?
4. **Trace formatı:** Hangi alanlar kesin gerekli, builder'ın içindeki LLM çağrıları nasıl raporlanmalı?
5. **Teslim:** Dosya adlandırma, kod teslimi (repo bağlantısı veya zip), bağımlılıklar için beklenti.
6. **Builder modeli/aracı kısıtı:** "Any tool is fine" ama kullanım limiti veya kredi desteği var mı?
7. **Ham malzeme dosya türleri:** `.md` dışında mail (`.eml`), PDF, CSV gelebilir mi?

---

## 13. Riskler ve unutulmaması gerekenler

- **Oturum yanması:** `close_call` her çağrı sonunda çalışıyor, taze oturum şart.
- **Judge gürültüsü:** Doğru agent bile bir koşuda kalabilir, bu yüzden tek koşuya güvenme.
- **Slot durumu:** `.freya-agents.json` aynı `slot` ile eski workflow'u günceller. Final için yeni ve temiz bir slot adı kullan, prova çıktılarını karıştırma.
- **200 workflow sınırı:** Deney yaparken yerinde güncelle.
- **Sırlar:** `env.sh`, API anahtarları ve team key repoya, trace'e ve bu chate girmesin.
- **Team key:** Her zaman aynı kalsın.
- **Saat dilimi:** 17:00 UTC = 20:00 İstanbul, 20:00 UTC = 23:00 İstanbul.
- **Kit sürümü:** Şu an v3. Güncellenirse organizatörler e-posta atacak, kontrol et.
- **Python:** 3.10+.
- **`now` değişkeni:** Final değerlendirme farklı günlerde. Hiçbir tarih sabit olmasın.
- **Her yol bir `end_call` node'una ulaşmalı**, ve `close_call` son tool çağrısı olmalı.
- **Yavaş model:** Medyan tur 10 sn'yi aşarsa müşteri kapatıyor, prompt'ları kısa tut.
- **Sorun yaratan kombinasyonlar:** kimlik öncesi `get_account`, "kaydedildi" demeden `create_promise` başarısı, Brief B'de transfer sonrası not ekleme, promise sonrası text-message cümlesinin unutulması.
- **Henüz keşfedilmemiş:** platformdaki **Checks** düğmesi ve node `assertions` alanı. Düşük öncelik, 15 dakikalık bir keşif yeterli.
- **Hafta sonu yorgunluğu:** Gece boyunca yeni özellik eklemek yerine uyku ve Pazar öğleden sonra donmuş bir builder çok daha değerli.

---

## 14. Claude Code oturum düzeni

Önceki md konuşmamızın güncel hali:

**Klasör düzeni (öneri)**
- `builder/` (teslim edilen ürün): kod, `.claude/skills/`, `requirements`, `README`, `env.example`.
- `dev/` (builder'ın dışında): `CLAUDE.md`, `docs/TASK.md` (kuralların kelimesi kelimesine kopyası), `docs/ARCHITECTURE.md` (spec şeması ve modül sözleşmeleri), `docs/FREYA_API.md` (keşifler ve tuzaklar), `docs/EXPERIMENTS.md` (append-only deney günlüğü), `docs/DECISIONS.md`.

**Rol dağılımı (2-3 oturum yeter, çünkü simülasyonlar seri çalışıyor):**
1. Builder çekirdeği: spec çıkarma, kapsama denetimi, derleyici.
2. Doğrulama ve test: statik doğrulayıcı, yerel birim testleri, persona üretimi, teşhis döngüsü.
3. Gözden geçirici: diff'leri inceler, builder'ı kırmaya çalışır, aşırı uyum (overfit) ve uyum ihlali arar.

**Kurallar:** Her oturum kendi git worktree'sinde. Spec şeması ve eval çıktı formatı paralel çalışmadan önce dondurulur. Kritik kuralları (hardcode yasağı, secret taraması) md'ye ve hook'a birlikte koy. Superpowers'ın plan ve brainstorm ritüellerini küçük değişikliklerde atla. Kodu sen yazacaksın, oturumlar yardımcı.

---

## 15. Teslim öncesi son kontrol listesi

- [ ] Builder `(brief dosyaları)` → workflow, hiçbir elle adım yok.
- [ ] Brief'e özel hiçbir değer, kural veya isim kodda/prompt'ta yok (practice brief'lere ait olanlar dahil, genelleme için).
- [ ] Süre sınırı: koşu < 30 dk, duvar saati koruması var.
- [ ] Her final brief için `export_workflow` çıktısı alındı.
- [ ] Trace: başlangıç/bitiş, her model çağrısı, Freya'da oluşturulanlar, testler.
- [ ] Repo ve trace'te anahtar yok.
- [ ] Bağımlılıklar sabitlenmiş, çalıştırma talimatı net (Python sürümü, env değişkenleri, tek komut).
- [ ] Kod etiketi (git tag) ve sürüm notu.
- [ ] Prova koşusu başarıyla bitti.
- [ ] Teslim e-postasındaki adımlar okundu ve 22:30'dan önce gönderildi.

---

Bir sonraki adım olarak sana önerim, Aşama 0'ı hemen yapmak: baseline koşusunu al, maliyeti ve süreyi ölç, bir manuel chat denemesi yap. Sonuçları (skor, süre, bakiye farkı, Anthropic maliyeti) buraya yazarsan E1 ve birim maliyet tahminlerini gerçek verilerle güncelleyip bir sonraki kararları birlikte verelim.
