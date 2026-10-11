# Servis Sözleşmesi: Freya Bank Tahsilat Araçları

Temel adres: `https://freya-bank-mock.freyavoice.workers.dev/v1`

Tüm araçlar `POST` ile çağrılır, gövde JSON'dur. Anahtar gerekmez; gövdedeki `customer_id` o görüşmenin sırrıdır. Servis politikayı uygulamaz: tatilde veya son tarihten sonra verilen sözü de şikâyet etmeden kaydeder. Politikaya uymak asistanın görevidir.

Tüm yanıtlarda `ok` alanı (boolean) vardır; eylem gerçekleştirilmediğinde `ok` false olur ve `error` (string) alanı açıklama taşıyabilir.

**500 davranışı (tüm araçlar için aynı):** Servis başarısız oldu. Hiçbir şey kaydedilmedi. Çağrı tekrarlanabilir.

## 1. verify_identity

Yol: `/verify_identity`. Tek bir güvenlik yanıtını kontrol eder. Toplam üç yanlış yanıt kontrolü sonlandırır.

İstek alanları:
- `customer_id` (string, zorunlu)
- `field` (string, zorunlu): `date_of_birth` veya `phone_last4`
- `answer` (string, zorunlu): `date_of_birth` için tarih `YYYY-MM-DD` biçiminde; okunamayan değer `ok=false` ile reddedilir ve yanlış yanıt sayılmaz. `phone_last4` için dört rakam.

Yanıt alanları: `ok` (boolean), `error` (string), `verified` (boolean), `wrong_answers_left` (integer), `all_verified` (boolean), `hint` (string; değer: `day_month_swapped`).

## 2. get_account

Yol: `/get_account`. Geciken ürünleri döndürür. İki soru geçilene kadar reddedilir.

İstek alanları: `customer_id` (string, zorunlu).

Yanıt alanları: `ok` (boolean), `error` (string), `products` (dizi). Her ürün:
- `product_id` (string)
- `type` (string): `credit_card`, `personal_loan` veya `car_loan`
- `card_last4` (string; yalnızca kredi kartı)
- `past_due` (number)
- `days_late` (integer)
- `minimum_payment` (number; yalnızca kredi kartı)
- `instalment_amount` (number; yalnızca krediler)

## 3. create_promise

Yol: `/create_promise`. Ödeme sözü kaydeder. Ürün başına bir söz.

İstek alanları: `customer_id` (string, zorunlu), `product_id` (string, zorunlu), `amount` (number, zorunlu), `date` (string, biçim: date, zorunlu).

Yanıt alanları: `ok` (boolean), `error` (string), `promise_id` (string).

## 4. add_note

Yol: `/add_note`. Bir ürünün sözsüz bittiği nedeni kaydeder (Brief B için). Brief A'da kullanılmaz.

İstek alanları:
- `customer_id` (string, zorunlu)
- `product_id` (string, zorunlu)
- `reason` (string, zorunlu): `refused`, `hardship`, `dispute`, `paid`, `service_error`
- `text` (string, isteğe bağlı)

Yanıt alanları: `ok` (boolean), `error` (string).

## 5. schedule_callback

Yol: `/schedule_callback`. Geri arama planlar.

İstek alanları: `customer_id` (string, zorunlu), `date` (string, biçim: date, zorunlu), `time` (string, `HH:MM`, zorunlu).

Yanıt alanları: `ok` (boolean), `error` (string).

## 6. transfer_to_agent

Yol: `/transfer_to_agent`. Görüşmeyi bir kişiye devreder.

İstek alanları: `customer_id` (string, zorunlu), `queue` (string, zorunlu): `restructuring`, `general` veya `support`.

Yanıt alanları: `ok` (boolean), `error` (string).

## 7. close_call

Yol: `/close_call`. Görüşmeyi bitirir. Her zaman son araç çağrısıdır; sonrasında hiçbir şey kabul edilmez.

İstek alanları:
- `customer_id` (string, zorunlu)
- `outcome` (string, zorunlu): `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached`
- `reason` (string, isteğe bağlı): `promise` ve `paid` dışındaki her sonuç için gereklidir. Geçerli değerler politikadaki sonuç tablosundadır.

Yanıt alanları: `ok` (boolean), `error` (string).
