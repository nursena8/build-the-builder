# HANDOFF: Build the Builder (teknik devir dokümanı)

Yeni bir Claude Code oturumu bu dosyayı okuyarak kaldığımız yerden devam eder. Sahip: Sena (sena@brainy.studio). Son güncelleme: 2026-10-10 (Cumartesi akşamı, İstanbul). Durum etiketleri: **[doğrulandı]** kendi ölçümüm/okumam, **[mentor]** mentorun aktardığı, doğrulamadım, **[doğrulanmadı]**.

Eski, daha genel doküman: `yapay_zeka_ile_konuştuğumuz_kısım.md` (mentorun ana başvuru dokümanı; bazı maddeleri güncel değil, bkz. §9).

---

## 0. Sana ilk 2 dakikada gerekenler

- **Hackathon:** Freya x YC "Build the Builder", online, 10-11 Ekim 2026. Hidden briefler Pazar 17:00 UTC (20:00 İstanbul), teslim 20:00 UTC (23:00 İstanbul) **[mentor+sayfa]**.
- **Görev:** Bir tahsilat (debt collection) brief'ini + banka tool API'sini (openapi) okuyup Freya'da telefon agent'ı (workflow JSON) üreten bir **builder** yazmak. Elle düzenleme yok.
- **Skor:** geçen vaka / çalışan vaka. Final: 2 hidden brief (biri temiz, biri ham malzeme) x 30 müşteri, her vakanın **3 tekrarının üçü de** geçmeli, skor /60. Vaka başına üç kontrol: outcome (ledger), policy, honesty (judge). Kısmi puan yok.
- **Rol dağılımı:** "Mentor" = Sena'nın konuştuğu ayrı bir Claude oturumu ("üst akıl"). Sen (Claude Code) mentorun brief'lerini uygular, Sena üzerinden rapor verirsin. **Mentor halüsinasyon yapabilir**; iddialarını dosyalarla kontrol et. Sena Freya UI'ına arada bakar; ondan bir şey gerekiyorsa açıkça söyle.
- **Şu an bekleyen:** Sena `--reps 3` koşusunu kendi terminalinde yapıyor (komut §6). Sonucu mentora yapıştıracak ("reps bitti"). Sen vaka bazlı analiz yapacaksın (hangi vaka 3/3, hangisi hangi nedenle düşüyor). **Reps-3'ü kendin başlatma.**

## 1. Değişmez kurallar (oturum kuralları)

1. Kit dosyalarını DEĞİŞTİRME: `tools/`, `examples/`, `docs/`, `briefs/`, `public-test-set.json`, `freya.py`, `README.md`. Yeni dosyalar sadece `dev/` altında (ve ileride `builder/`, `runs/`).
2. API anahtarlarını (FREYA_API_KEY, FREYA_BANK_TEAM_KEY, GEMINI_API_KEY) hiçbir çıktıya/loga/dosyaya (env.sh hariç)/commit'e yazma. `.gitignore`: env.sh, .freya-agents.json, .personas.json, results/, traces/, out/, __pycache__/, .DS_Store, .venv/.
3. Yeni bağımlılık kurma (talimat olmadan). Gemini çağrıları stdlib `urllib` ile.
4. Doğrulayamadığını "doğrulanmadı" diye yaz. Transkriptleri kelimesi kelimesine alıntıla, yorumu ayır.
5. Skorun tek kaynağı `run_cases.py` çıktısı ve `results/` dosyaları. **Freya arayüzündeki "Checks" paneli hakkında yorum yapma, skor diye raporlama.**
6. Mentor onayı olmadan simülasyon başlatma. `--reps 3` ve ağır builder koşuları Sena'nın **kendi terminalinde** çalışır (Claude Code içinde değil; kota koruması).
7. Mock bankaya (practice/sessions, ledger) **sadece PUB-01..PUB-13** id'leriyle istek at. Yeni/bilinmeyen id gönderme ("platform probing" yasağı).
8. Sayfa kuralı: "Do not probe or load-test the platform." Gereksiz çağrı yapma. Freya bakiye okuma rotası dokümante değil, deneme.
9. Her anlamlı deney `dev/EXPERIMENTS.md`'ye bir satır (append-only). Commit mesajlarının sonuna: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
10. Shell'de `$` içeren metni echo ile yazma (tek tırnaklı heredoc kullan; bir kez "$99.99" bozuldu).

## 2. Yarışma kuralları (kaynak: `dev/TASK.md`)

Bkz. `dev/TASK.md` (tek doğruluk kaynağı). Özet:
- Giriş komutu **[mentor, sayfada göremedim]**: `python3 builder/build.py {brief_path} {tool_api_path}`, çıktı `tee traces/<brief>.log`.
- Teslim formu **[WebFetch ile doğrulandı]**: takım adı, repo URL, commit hash, run_command, workflow dosya yolları, trace dosya yolları. Brief başına bir phone agent, "one commit", workflow'lar `freya.export_workflow` ile. Trace düz metin olabilir.
- Doğrulama: ilk 10 takımın teslimi yeniden build edilip trace'lerle karşılaştırılır **[WebFetch: "Top ten teams' submissions rebuilt and compared against traces"]**. Reviewer-agent ve "belirgin düşük skor -> silinir" ayrıntıları **[mentor]**.
- Yasaklar **[WebFetch ile doğrulandı]**: platformu probe/load-test etme; takım başına 1 Freya key; phone agent kit tool API'si dışında servis çağırırsa vaka düşer; elle yapılmış agent teslim edilemez; hidden brief'ten hiçbir şey builder'a yazılamaz; 1 veya 2 kişilik takım.
- Limitler: builder süresi brief başına 30 dk; aynı model herkeste. **Workflow limiti ÇELİŞKİLİ:** mentor "10" dedi, benim WebFetch'im (Rules) ve README "200" diyor. Kesin değil: az workflow, yerinde güncelle.
- Tie-break sırası **[WebFetch ile doğrulandı]**: (1) geçen vakalardaki toplam promise tutarı, (2) trace'ten build süresi, (3) daha erken teslim.
- Leaderboard **[WebFetch]**: "Nothing is scored yet", hidden benchmark ve doğrulamadan sonra görünür. Yani şimdi sıralama yok.
- Practice vakalar: 13 (A: 10, B: 3), hepsi `now = 2026-10-14T11:00`, Çarşamba.

## 3. Ortam

- macOS, Python 3.14.0 (Homebrew, PEP 668 -> sistem pip'i kullanma). `.venv` var; claude-agent-sdk venv'de kurulu. Çalıştırma öncesi: `source env.sh && source .venv/bin/activate`.
- Proje: `/Users/sena/Documents/build the builder/build-the-builder/` (git repo; Claude Code'un env satırı "git repo: false" diyebilir, yine de `git log` çalışır).
- `env.sh` (gitignored): FREYA_API_KEY, FREYA_BANK_TEAM_KEY (24 karakter, her seferinde aynı), GEMINI_API_KEY dolu. FREYA_API_URL=https://staging-app.freyavoice.ai. ANTHROPIC_API_KEY set değil (builder Sena'nın Claude aboneliği girişiyle çalıştı; Sena'nın kendi terminalindeki durumu doğrulanmadı).
- Banka mock: `https://freya-bank-mock.freyavoice.workers.dev/v1`, başlık `x-team-key`.
- Slotlar (`.freya-agents.json`, gitignored): `base` workflow fbf7e2b0-4d71-4f6d-b9ba-8a569714d084 / agent b60b43aa-b227-455f-8dc7-c1ecd6df8161; `brief-a` workflow 0945c087-fd58-4b0e-af24-0d4f14e974d6 / agent **a1041f0f-763b-4eab-907a-c2b2efafa432** (v3 yayınlı). Organizatörün orijinal workflow'u dahil workspace'te 3 workflow var **[mentor]**.
- Git: bf45813 v0-kit; 291d247 baseline; 58b7219 Gemini testi; 82a0891 reference/mutant; 1435fef TASK.md + PUB-10 + extra vakalar.
- Freya bakiyesi başlangıçta $99.99 (UI). Harcama ölçülmedi: Sena bakiyeyi reps-3 öncesi/sonrası not edecek.

## 4. Kit anatomisi (kısa)

- `freya.py`: stdlib istemci. `save_workflow(slot, wf)` (oluştur/güncelle + yayınla), `update_workflow`, `export_workflow(id, path)`, `run_simulation`, `get_iteration`, `get_call`, `create_personas`, `validate_workflow` (dryRun). `AGENT_LLM` = experimental-5, değiştirme. Judge/persona modeli Gemini 3 Flash.
- `tools/run_cases.py`: `python3 tools/run_cases.py <agent_id> --brief A|B [--only IDs] [--reps N] [--style pieces|corrects|talkative|asks_back|in_words] [--out f.json] [--cases file] [--rerun-if-slow N]`. Her koşuda her vaka için `/v1/practice/sessions` ile taze müşteri alır, simülasyon koşar, ledger'ı `score.py` ile skorlar, judge sonucunu ekler. `results/log.jsonl`'e bir satır ekler. Vaka sayılması için hepsi geçmeli; `--reps 3` ile 3/3 şart.
- `tools/score.py` ledger skoru: (outcome, reason) birebir (reason yoksa None); promise (product_id, tutar, tarih); not (product_id, reason); callback (tarih, saat); transfer queue; son tool `close_call`; `not_reached` vakada verify/get_account çağrısı ihlal; kimlik doğrulanmadan get_account/create_promise ihlal.
- Banka tool'ları: verify_identity, get_account, create_promise, add_note, schedule_callback, transfer_to_agent, close_call. close_call sonrası o müşteri oturumu tek kullanımlık yanar. Mock servis kurallarını uygulamaz (tatilde promise kabul eder). `PUB-10` faults: create_promise ilk çağrıda 500 ("service unavailable, nothing was recorded").
- `docs/*.md` (workflow-format, tools-and-code) bu oturumlarda **okunmadı** (kota). Platform tuzakları için ana doküman §3.2 tablosuna bak **[mentor]**.
- Brief A: 47 kural (tarih kuralları `now`'dan; bantlar: days_late 1-7 erken -> 12. iş günü 1 deneme; 8-45 geç -> 7. iş günü 2 deneme; tatiller 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01; callback 10:00-19:00 dahil, `now`'dan sonra). Brief B: çok ürünlü akış.
- Brief A kural 1: açılışta "this call is recorded" zorunlu **[doğrulandı: transkriptlerde]**.

## 5. Ne yaptık, hangi sonuçlar var (kronolojik)

### 5.1 Baseline (base agent, Brief A)
0/10, 222 sn. Yapısal hatalar: eksik tool'lar, eksik enum değerleri, tarih mantığı yok, PUB-03'te 70+ tekrar döngüsü, PUB-10'da retry yok. (Mentorun "~2/13" tahmini Brief A+B içindi; Brief A için 0/10.)

### 5.2 Gemini ile spec çıkarma testi (`dev/gemini_spec_test.py`)
- Kullanım: `source env.sh && python3 dev/gemini_spec_test.py <model> <thinking_level> <dest.json>`. stdlib; meta `dev/llm-calls.jsonl`'a (anahtar/prompt yok).
- Flash (low): 29.1 sn, 6361 giriş / 4663 çıkış, `dev/spec-a-flash.json` 15.8 KB, 47 kuraldan 41'i. Pro (low): 12.0 sn, `dev/spec-a-pro.json` 5.1 KB, 36/47.
- İkisi de kaçırdı: kurallar 19/20/21/23/29 (tarih-pazarlık). Flash kural 17 içeriğini kaçırdı; Pro ayrıca 31/32/33/35/36.
- `generationConfig.thinkingConfig.thinkingLevel` HTTP 200 verdi ama resmi doküman yeni "interactions" API'sini anlatıyor; alan adları **[doğrulanmadı]**.
- Çıkarım: LLM spec çıkarma tek başına yetmez, ayrı kapsama denetimi geçişi şart.

### 5.3 Sample builder (Claude Agent SDK, Sena'nın terminalinde)
- 20 tur, 658 sn, **$1.10**, 16 model çağrısı (claude-sonnet-5-5) + 1 küçük haiku çağrısı. API zamanı 267.6 sn. Çıkış 36,189 token (20,594 düşünme). Trace: `traces/20261010-180039.jsonl` (gitignored). **Trace'te zaman damgası ve "model + amaç" satırı yok**; yarışma bunu istiyor, kendi trace yazıcımız şart.
- Log: `dev/sample-builder-a.log`. Builder `dev/gen_brief_a.py` (33.6 KB) üretici betiği yazdı: Brief A değerleri (tatiller, `addbd(today,12)`, 10:00-19:00) **koda gömülü**. Hidden brief için yeniden kullanılamaz, ve brief değerlerini koda yazmak yasak; bu yaklaşım sadece referanstır.
- Ürettiği agent (`dev/reference/sample-a.workflow.json`, 92 KB): 23 node (4 conversation: confirm_name, security, third_party, debt; 17 code: prepare + 16 close_*; 1 api_request load_account; 1 end_call hangup), 41 geçiş (14 matches_intent). Tarih gerçekleri `prepare` code node'unda hesaplanıp prompta yazılıyor; outcome/reason code node'larında hesaplanıp workflow seviyesi `close_call` (alwaysRunsAt end_of_call) parametrelerine veriliyor. Döngü koruması: debt max_node_turns 80, security 25, third_party 10, confirm_name 10. En büyük prompt debt (4907 karakter). Tool'lar yalnızca conversation node'larında (debt: create_promise + 3 transfer; security: verify_identity; third_party: schedule_callback), get_account pre_action.
- Platform export vs kaydettiğimiz: fark yalnız platformun eklediği `mode:"exact"` ve `agent_config` (experimental-5, temperature **0.7**, maxTokens 1000) **[doğrulandı]**. Yayınlı v3 içeriği API'den doğrudan okunamadı; export updated_at ile v3 zamanı örtüşüyor (dolaylı).

### 5.4 Skor geçmişi, Brief A, 10 vaka (`results/log.jsonl`)

| Koşu | Sürüm | Skor | Kalan | Süre |
|---|---|---|---|---|
| baseline | base | 0/10 | hepsi | 222 sn |
| 1 | v1 | 9/10 | PUB-07 (26 Ekim yerine 2 Kasım teklif) | 85 sn |
| 2 | v2 | 7/10 | PUB-04, 07, 10 | 96 sn |
| 3 | v3 | 9/10 | PUB-10 | 85 sn |
| 4 (`--only PUB-10`) | v3 | 0/1 | PUB-10 | 74 sn |

- Tam koşular `--out` olmadan koşulduğu için vaka bazlı JSON yok; nedenler trace'ten kurtarıldı.
- **Koşular hızlı** (10 vaka ~75-96 sn); mentorun "3-11 dk" varsayımı fazla kötümserdi. README yoğun saatlerde 11 dk'ya kadar çıkabilir diyor.
- Tek koşu skoruna güvenme; v1->v2->v3 farklı vakalarda oynadı (gürültü mü yama mı ayırt edilemedi).

### 5.5 PUB-10 analizi (judge gürültüsü) **[doğrulandı, transkript]**
- v1 (call 654b3fe2…) PASS, v3 (call 94527152…) FAIL. Ham: `dev/pub10-v1-v3.json`.
- Açılış iki koşuda birebir: "Hello, I am a digital assistant calling from Freya Bank, and this call is recorded. Am I speaking with Ms Lin?"
- create_promise #1 -> hata ("service unavailable, nothing was recorded"), #2 -> ok. v1 hata sonrası: "...the system encountered an error and the promise was not recorded. Let me try that again for you." v3: "...I was unable to record that promise due to a system error. Let me try one more time for you."
- Judge v1: Message 0 ve 12'deki "recorded"ı gördü, geçirdi. Judge v3: Message 0'ı "literal" ihlal saydı.
- Sonuç: aynı davranışa farklı hüküm = judge gürültüsü. "v2'deki recorded yasağı bozdu" tezi desteklenmedi (örnek az). Banka tarafı iki koşuda da doğru (tek promise).
- Mentorun kararı: judge'a dokunulmaz; açılıştaki "recorded" brief gereği sabit; hata sonrası mesajda "record" kelimesi kullanılmasın ("I couldn't save it, let me try again"); "recorded" sadece ok:true sonrası; sonra `--reps` ile ölç. v1 kanıtı bunun tek başına belirleyici olmadığını gösteriyor, etkisi ölçülmeli.

### 5.6 Mutant genelleme testi (tasarlandı, **çalıştırılmadı**)
- `dev/mutant/brief-a-mutant.md`: Brief A'dan yalnızca şunlar değişti: callback penceresi 09:00-17:00; tatiller 2026-10-20, 2026-11-03, 2026-11-19, 2026-12-24, 2027-01-04; erken bant 10. iş günü; geç bant 5. iş günü. İkna denemeleri aynı.
- `dev/mutant/bizdays.py` ile now=Çar 2026-10-14: geç deadline **22 Ekim**, erken deadline **29 Ekim**.
- `dev/mutant/cases-mutant.json` (Brief A, 10 vaka): PUB-04 beklenen 10-23 -> **10-22**; PUB-07 10-27 -> **10-26**; diğer 8 aynı. Zayıflık: 09-17 penceresi ve 10-20 tatili hiçbir mevcut vakada test edilmiyor.
- `dev/mutant/cases-mutant-extra.json` (2 vaka, mevcut id'lerle, yeni id yok): PUB-07 hesabıyla "Tuesday the 20th" -> promise **2026-10-21**; PUB-02 hesabıyla 17:30 sonra 18:00 -> `not_reached`/`no_callback`, callback yok. Mock'un bu id'ler için bant/tutar verisi **[doğrulanmadı]** (get_account verify gerektirir); yalnız isim ve `now` practice/sessions ile doğrulandı.
- **Tuzak:** Mutant brief ile builder koşarsan `--cases dev/mutant/cases-mutant.json` ver; varsayılan vakalar eski beklentilerle skorlar. Sample skill'in test adımı public vakaları kullanıyor.

## 6. Sıradaki adım: reps-3 (Sena çalıştırıyor)

```
cd "/Users/sena/Documents/build the builder/build-the-builder" && source env.sh && source .venv/bin/activate && python3 tools/run_cases.py a1041f0f-763b-4eab-907a-c2b2efafa432 --brief A --reps 3 --out results/ref-a-reps3.json 2>&1 | tee dev/ref-a-reps3.log
```
3 ardışık simülasyon, ~5 dk. Çıktılar: `results/ref-a-reps3.json`, `dev/ref-a-reps3.log`, `results/log.jsonl`. Sena bakiyeyi öncesi/sonrası, `/usage` yüzdesini yazacak. Ona kadar Freya'da simülasyon başlatma, UI'da Re-run yok.

Sonuç gelince yapılacak (mentor talebi): vaka bazlı analiz: hangi vaka 3/3; düşen vaka hangi nedenle (judge gürültüsü / tool sırası / tarih / outcome). `--out` JSON'undaki `call_id`'lerle `freya.get_call` üzerinden transkript çek (okuma, simülasyon değil). Bu veriyle mentor v1'in ilk işini seçecek.

## 7. Builder tasarım yönü (karar bekleyen/bağlayıcı)

**Bağlayıcı kısıtlar (mentor):** giriş `builder/build.py <brief> <openapi>`; trace zaman damgalı satırlar halinde stdout'a; model anahtarları yalnız ortam değişkeninden (Claude girişine bağımlılık yok: doğrulama koşusunda organizatörün ortamında çalışması gerek); brief'e özel üretilen dosyalar kod ağacından ayrı `runs/<brief>/` altına.

**Mimari fikri (ana doküman §6):** brief -> spec (sabit şemalı JSON) -> kapsama denetimi (ayrı LLM geçişi) -> deterministik derleme (şablonlar) -> statik doğrulama (kod: null yok, tools doğru node türünde, passthrough'ta always, kodda `{{` yok, boolean routing yok, tool alanları/enum'lar openapi ile birebir, her yol end_call'a ulaşır) -> `validate_workflow` -> kaydet/yayınla -> hızlı testler -> yama -> en iyi sürümü sakla -> `export_workflow`. Kuralları prompta değil en sağlam mekanizmaya koy: tarih/outcome/tutar kodda, sabit cümleler sabit TTS veya hook `what_to_do_next`, sayaçlar kod değişkenlerinde.

**Gerekçe (referans builder gözleminden):** sample builder her koşuda kendi üretici betiğini doğaçlama yazıyor (varyans), brief değerlerini koda gömüyor, trace'i yok, en iyi sürümü saklamıyor, wall-clock koruması yok. Hidden brief değerleri repoya yazılırsa yasak ihlali olur.

**Açık sorular (destek kanalı, yanıt yok):** doğrulama koşusunda hangi model anahtarı; hidden brief için mock bankadan test oturumu nasıl alınır (practice/sessions yalnız PUB id'lerini tanıyor); formdaki commit builder'ın son commit'i mi; workflow limiti 10 mu 200 mü; `agent_config.temperature` değiştirilebilir mi (varsayılan 0.7; organizatör izni gerekli, deney E6).

## 8. Bilinen riskler

- Judge gürültüsü: 3/3 şartı her vakada bu riski çarpar (PUB-10 örneği).
- Tarih mantığında model müşterinin söylediği tarihi seçiyor, kod doğrulamıyor (sample agent'ta). PUB-04/07 oynaması buradan olabilir **[doğrulanmadı]**.
- Hidden briefte yeni kimlik alanları (postcode, birth_year, company_number, founded_year: run_cases.py'de hazır), farklı iş günü tanımı/tatiller, 1-3 ürün, ham malzeme (mail, memo, kod listesi), müşteri konuşma tarzları (sayıyı parçalı söyleme, kendini düzeltme, soru sorma, sözle tutar/tarih).
- Anthropic kotası: Sena'nın kota endişesi var; ağır koşular onun terminalinde, final koşuları için kota/anahtar planı gerek.
- Trace'te anahtar sızıntısı: commit öncesi tara.

## 9. Ana dokümanın güncel olmayan maddeleri

`yapay_zeka_ile_konuştuğumuz_kısım.md` içinde: "ikinci workspace ile paralel koşu" (geri alındı: takım başına 1 workspace/key); simülasyon süreleri ("3-11 dk" fazla kötümser, ~85 sn ölçüldü); giriş komutu ve trace içeriği (bkz. §2); "probing" kuralı (var); workflow limiti (çelişkili). "~2/13 baseline" Brief A+B içindi.

## 10. Dosya haritası

- `dev/TASK.md` resmi kurallar; `dev/EXPERIMENTS.md` deney günlüğü (append-only); `dev/HANDOFF.md` bu dosya.
- `dev/gemini_spec_test.py`, `dev/spec-a-flash.json`, `dev/spec-a-pro.json`, `dev/llm-calls.jsonl`.
- `dev/sample-builder-a.log`, `dev/gen_brief_a.py` (referans, brief'e gömülü), `dev/reference/sample-a.workflow.json`.
- `dev/pub10-v1-v3.json` PUB-10 transkriptleri.
- `dev/mutant/{brief-a-mutant.md, bizdays.py, cases-mutant.json, cases-mutant-extra.json}`.
- Gitignored: `env.sh`, `.freya-agents.json`, `.personas.json`, `results/`, `traces/`, `out/`.

## 11. Yeni oturumun ilk işleri (öneri)

1. `git log --oneline`, `dev/EXPERIMENTS.md` ve bu dosyayı oku. Sena'ya reps-3 durumunu sor.
2. `results/ref-a-reps3.json` varsa vaka bazlı analiz yap (§6), EXPERIMENTS.md'ye satır ekle, commit.
3. Mentor v1 işini seçmeden builder kodu yazmaya başlama. Seçilince: `builder/build.py`, zaman damgalı trace yazıcı, `runs/<brief>/` çıktı dizini, statik doğrulayıcı.
