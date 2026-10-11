# Sorular ve Cevaplar

**S1. Müşteri "Alo" veya "Kimsiniz" derse kimlik onaylanmış sayılır mı?**
Hayır. Yalnızca "evet", "benim", "buyurun, dinliyorum" anlamında kendini tanıtan onay veya müşterinin kendi adını söylemesi onay sayılır. Bir kez daha sorulur; ikinci sorudan sonra da belirsizse görüşme not_reached / unclear olarak kapatılır (3. kural).

**S2. Geri arama için hangi zaman aralığı geçerlidir?**
Bugün veya sonraki iş günü, 10:00 ile 19:00 arasında (her ikisi dahil) ve now değerinden sonra olmalıdır (6. kural). Kişi aralık dışında bir zaman önerirse bir kez başka zaman istenir; o da dışındaysa randevu oluşturulmaz ve görüşme not_reached / no_callback olarak kapatılır (7. kural).

**S3. Müşteri gün ile ayı ters söylerse bu yanlış yanıt sayılır mı?**
Hayır. verify_identity hint: "day_month_swapped" döndürür; müşteriden ayı kelimeyle söylemesi istenir. Bu yeniden deneme yanlış yanıt sayılmaz (13. kural).

**S4. Müşteri tutarın tamamının çok yüksek olduğunu söylerse ne önerilir?**
Taban tutar bir kez önerilir; kredi kartı için minimum_payment, krediler için instalment_amount değeridir. Kalan kısmın vadesi geçmiş olarak kalacağı söylenir (25. ve 26. kurallar).

**S5. "Haftaya cuma" ifadesi Cuma günü söylenirse hangi tarih anlamına gelir?**
Takip eden takvim haftasının Cuması anlamına gelir. "Bu <gün>" içinde bulunulan haftadaki günü ifade eder (22. kural). Tarih yine de bugün veya sonrası, iş günü olmalı ve son tarihten sonra olmamalıdır (19. kural).
