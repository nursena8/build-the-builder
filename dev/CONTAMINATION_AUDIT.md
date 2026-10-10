# Kirlenme denetimi: builder A+B koşusu (traces/20261010-201310.jsonl) (İŞ 1, Adım 5B)

Yöntem: trace'teki AssistantMessage ToolUseBlock girdileri (Read/Bash/Write), `dev/|results|traces|out/|freya-agents|git log` desenine uyanlar. 11 eşleşme. Trace'te düşünme metni yok (thinking blokları boş/gizli), bu yüzden "builder şunu okuyup şunu yaptı" nedenselliği kanıtlanamaz; yalnızca erişim ve metin örtüşmesi gösterilir.

## Erişilen dosyalar

| Satır | Araç | Komut/dosya | Kapsam | Kategori |
|---|---|---|---|---|
| 8 | Bash | `cat briefs/brief-a.md; cat briefs/brief-b.md` (+ ls -R briefs tools docs examples out) | tam | (a) amaçlanan |
| 32 | Bash | `git log --oneline \| head; git status --short; ls -la out; cat tools/run_cases.py; ls` | git log: 10 satır; run_cases tam | (a)+(c) git log |
| 50 | Bash | `ls dev results traces \| head -50` ve `out/brief-a.workflow.json` (eski çıktı) düğüm/tool listesi | dosya adları + yapı | (b) adlar, (c) out/ |
| 55 | Bash | `cat dev/HANDOFF.md; cat dev/EXPERIMENTS.md \| head -300; cat results/log.jsonl` | **tam** HANDOFF, EXPERIMENTS ilk 300 satır, log tam | (b) + (c) |
| 63 | Bash | `cat .freya-agents.json` (ilk 1500 karakter), `grep -n "def " freya.py`, `cat tools/score.py \| head -80` | kısmi | (c) + (a) |
| 116 | Bash | `dev/reference/sample-a.workflow.json`: `load_account` düğümü (ilk 3000 kr), `prepare` kodu (ilk 6000 kr) | kısmi | (b) referans workflow |
| 118 | Bash | aynı dosya, yeniden (`w['workflow']` ile) | kısmi | (b) |
| 222 | Write | `dev/gen_phone_agents.py` (çıktı) | - | çıktı |
| 229, 237, 244 | Bash | üretici çalıştırma, `freya.save_workflow`, `run_cases.py` | - | iş |

Okunmadığı doğrulananlar: `dev/GEN_BRIEF_A_CONSTANTS.md`, `dev/gen_brief_a.py`, `dev/mutant/*`, `results/ref-a-reps3.json`, `dev/pub10-v1-v3.json` (trace'te yol eşleşmesi yok). `ref-a-reps3` kelimesi trace'te EXPERIMENTS/HANDOFF çıktısı içinde geçtiği için görünüyor.

## Örtüşmeler (alıntıyla)

1. **Bant/deadline kodda, modele tek gerçek.** Builder'ın tam okuduğu `HANDOFF.md` §12: "Neden: `prepare` iki deadline'ı da prompta yazıyor, seçim `debt` prompt'unda modele bırakılmış (gen_brief_a.py satır 465)." ve "Kural: tool sonucuna veya brief değerine bağlı her seçim (bant, deadline, floor, deneme sayısı) kodda yapılsın, modele tek net gerçek verilsin." Üretici betikte: `account_facts` code node'u `get_account`'tan sonra ürün başına bandı seçiyor (satır 296-304: `days = int(float(p.get('days_late')))`, `if days <= 7: band='early' ... else: band='late'`), prompta "ACCOUNT FACTS ... (computed by code; trust them, never compute your own). Each product has its OWN band, deadline, floor and number of persuasion attempts" (satır 458, 487). Bu, HANDOFF'taki bulguyla birebir örtüşüyor. Bağımsız bulma mı yoksa okuyup uygulama mı: **ayırt edilemiyor, doğrulanmadı**. (İlk sample koşusu ve builder'ın reference workflow'u iki deadline'ı prompta yazıyordu; bu koşuda değişti.)
2. **Yapı iskeleti reference workflow'dan.** Okunan `sample-a.workflow.json`: `prepare` code node'u, `load_account` api_request, `close_*` code node'ları, hook'lar (`what_to_do_next`), `hangup` end_call, workflow seviyesi `close_call` (alwaysRunsAt end_of_call). Üreticide aynı yapı (satır 346-405, 593-599, 627-640). İlk sample builder (temiz) de aynı yapıyı çıkarmıştı, yani yapı örtüşmesi tek başına kirlenme sayılmaz.
3. **PUB-10.** HANDOFF §5.5 judge gürültüsünü anlatıyor. Üreticide hata sonrası metin "technical problem ... try once more" (satır 128) ve "Never say a promise is recorded unless its result says so"; HANDOFF'taki "hata sonrası mesajda 'record' kullanma" önerisiyle uyumlu, ama sample-a'da da benzer yasak vardı (gen_brief_a.py satır 494).
4. **Sabit cümleler/TTS**: gen_brief_a.py'de ve brief'te zaten var; HANDOFF'a bağlı değil.

## Sonuç
Skor (A 10/10, B 3/3 tek koşu) referans olarak yazılmadı. Kirlenme olasılığı yüksek (madde 1 doğrudan HANDOFF cümlesine dayanıyor). Etkiyi ölçmek için dev/ notları olmayan temiz dizinde yeniden koşu gerekir (mentor planı: mutant + temiz klon).
