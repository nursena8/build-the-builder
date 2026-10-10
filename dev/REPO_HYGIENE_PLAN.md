# Repo hijyeni PLANI (uygulanmadı) (İŞ 4, Adım 5B)

Sorun: `examples/agent_builder.py` builder'ı `cwd=KIT` (repo kökü) ile çalıştırır ve Bash/Read ile her dosyaya erişebilir. Bu koşuda builder `dev/HANDOFF.md`, `EXPERIMENTS.md`, referans workflow'u okudu (bkz. CONTAMINATION_AUDIT.md). Organizatörler repo'yu commit'ten klonlayıp builder'ı çalıştıracak; commit'te dev notları varsa onların koşusu bizimkinden ayrışır. Hedef: submission commit'inde yalnızca builder'ın çalışması için gereken dosyalar olsun; dev notları builder'ın göremeyeceği bir yerde.

## Hedef düzen

Submission repo (commit'e giren):
```
builder/
  build.py            giriş: python3 builder/build.py <brief_path> <tool_api_path>
  freya.py            kit istemcisi (kopya; kit dosyası orijinali değiştirilmez)
  skills/ veya .claude/skills/   builder'ın bilgisi (brief'e özel değer yok)
  docs/               yalnız builder'ın okuyacağı platform doküman kopyaları
  helpers/            statik doğrulayıcı, trace yazıcı, zaman koruması
  requirements.txt, README.md, env.example
runs/<brief>/         builder çıktıları (workflow.json, trace, export); commit'e brief başına çıktılar girer, kod ağacından ayrı
```
Commit'e GİRMEYENLER (ayrı repo veya builder'ın cwd'si dışında bir klasör, örn. `~/builder-dev/`): `HANDOFF.md`, `EXPERIMENTS.md`, `TASK.md`, `CONTAMINATION_AUDIT.md`, `GEN_*_CONSTANTS.md`, `reference/` (sample-a workflow), `mutant/`, `gen_brief_a.py`, `gen_phone_agents.py` (brief A/B değerleri gömülü: hidden-brief kuralı ihlali riski), `results/`, `traces/` (dev koşuları), `spec-*.json`.

## Adım adım taşıma
1. Dev dosyalarının kopyası: `mkdir -p ~/builder-dev && git -C <repo> ls-files dev | ...` ile `dev/` içeriğini `~/builder-dev/` altına kopyala; ayrı bir git repo başlat (`git init ~/builder-dev`). Not defteri/log tutmaya oradan devam.
2. Geçmişi temizleme kararı: bu repoda `dev/` commit'leri var. Submission commit'i temiz olsa da git geçmişi `dev/` içeriğini taşır; klon geçmişle gelir. Seçenekler: (a) submission için yeni repo, `builder/` ve `runs/` ile temiz tek commit (öneri); (b) mevcut repoda `git rm -r dev` ve geçmişi tutmak (geçmiş okunabilir kalır, riskli). Kararı kullanıcı/mentor versin.
3. `builder/` iskeletini yeni repoda oluştur: `freya.py`'yi kit kökünden kopyala, skill'leri `builder/.claude/skills/` altına taşı (SDK `setting_sources=["project"]` ile `cwd`'deki `.claude/` okunur; `cwd`'yi `builder/` yap veya `build.py` içinde ayarla).
4. `build.py` içinde SDK `cwd`'sini geçici temiz bir çalışma klasörüne ayarla (brief ve openapi o klasöre kopyalanır); builder repo kökündeki başka dosyaları görmesin. Çıktılar `runs/<brief>/`.
5. Anahtarlar yalnız ortam değişkeninden okunur; `env.sh`/`.freya-agents.json` commit'e girmez (`.gitignore`). Slot dosyası runs altına değil, yerel kalır.
6. Hidden-brief hijyeni: `builder/` altında "Brief A/B'ye özel değer" taraması: tatil tarihleri (2026-..), "10:00"/"19:00", Brief A/B ismi, gen_*.py dosyaları yok. Basit bir `grep` kontrolü commit öncesi çalıştırılır.
7. Sır taraması: `grep -rE "fak_|AIza|sk-ant|x-team-key"` ve env.sh değerleri için commit öncesi kontrol.

## Temiz klon testi (komut dizisi; Sena'nın terminalinde, çalıştırılmadı)
```
set -e
D=$(mktemp -d) && cd "$D"
git clone <REPO_URL> repo && cd repo && git checkout <COMMIT_HASH>
python3 -m venv .venv && source .venv/bin/activate
pip install -r builder/requirements.txt
cp /path/to/env.sh . && source env.sh        # anahtarlar repoya girmez
python3 builder/build.py <brief_path> <tool_api_path> 2>&1 | tee traces/<brief>.log
```
Doğrulama: `runs/<brief>/` altında workflow ve export oluştu mu; `ls`/`find` ile builder'ın `dev/` göremediği; `grep` ile anahtar yok; süre < 30 dk; sonra `tools/run_cases.py`'yi (kit, ayrı kopyadan) üretilen agent'a karşı çalıştır. Not: `tools/run_cases.py` kit dosyası, submission repo'sunda bulunması şart değil (organizatörün aracı).

## Açık sorular (destek kanalı)
Commit'e builder kodu mu yoksa çıktılar ve trace de mi giriyor (formda "one commit"); doğrulama koşusunda hangi model anahtarı; `tools/` ve `docs/` kopyalarının submission'da olup olmaması.
