# TASK (resmi kurallar, hackathon sayfasından; tek doğruluk kaynağı)

Kaynak: mentorun aktardığı hackathon sayfası özeti (Overview/Data/Evaluation/Submit/Rules). Sayfayı kendim okumadım: doğrulanmadı.

- Giriş komutu: `python3 builder/build.py {brief_path} {tool_api_path}` (mentor: Submit bölümünde hem örnek komutta hem form JSON'unda var; WebFetch özetimde çıkmadı). Tek brief ve onun openapi dosyası. Çıktı `tee` ile `traces/<brief>.log`'a gider; trace builder'ın yazdırdıklarıdır.
- Trace içeriği (sayfa: koşunun başlangıç ve bitiş zamanını ister; satır başı zaman damgası bizim tercihimiz, şart değil): başlangıç ve bitiş zamanı; her model çağrısı (model + tek satır amaç); Freya'da oluşturulanlar (workflow id, agent id, node ve tool sayısı); kendi agent'ı üzerindeki testler ve sonuçları. Anahtarlar commit öncesi temizlenir. Trace'siz giriş sıralanmaz.
- Teslim: GitHub repo, commit, run_command, her brief için `freya.export_workflow` çıktısı, her brief için trace.
- Doğrulama: ilk 10 takımın repo'sunu organizatörler o commit'ten klonlayıp builder'ı aynı brieflerde çalıştırır. Kendi koşuları belirgin şekilde düşükse giriş silinir. Her trace bir reviewer agent tarafından koda ve oluşturulan agent'a karşı kontrol edilir ("How we verify" altında; mentor tam sayfa metninde doğruladı, silinme kuralı dahil).
- Limitler: builder koşusu brief başına en fazla 30 dk (kendi testleri dahil); workspace başına workflow limiti 200 (Sena sayfayı kendisi kontrol etti; README ile aynı). Aynı anda 1 simülasyon; takım başına 1 Freya key ve 1 workspace.
- Yasaklar: platformu probe veya load-test etme; phone agent kit tool API'si dışında servis çağıramaz; hidden brief'ten hiçbir kural, değer veya isim builder koduna/promptlarına yazılamaz; phone agent elle düzenlenemez.
- Final: 2 hidden brief x 30 müşteri (1-3 ürün, birkaç takvim günü), 3 tekrarın üçü de geçmeli, skor /60. Eşitlikte sırayla: geçen vakalardaki toplam promise tutarı, trace'ten okunan build süresi, erken teslim.

## Builder tasarımında bağlayıcı kısıtlar
1. Giriş `builder/build.py <brief> <openapi>`.
2. Trace zaman damgalı satırlar olarak stdout'a yazılır.
3. Model anahtarları sadece ortam değişkenlerinden okunur (Claude girişine bağımlılık yok).
4. Brief'e özel üretilen dosyalar kod ağacından ayrı `runs/<brief>/` altına yazılır.

## Açık sorular (destek kanalı)
Doğrulama koşusunda hangi model anahtarı; hidden brief için mock banka oturumu nasıl alınır; formdaki commit hangisi.
