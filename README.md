# MUHTEŞEM 13.yüzyıl — onaylı alıntı kartı yayınlayıcı

Her gün bir kart hazırlar, **Telegram'dan senin onayına** sunar. Hiçbir şey sen
onaylamadan Instagram'a gitmez. GitHub'a girmene gerek yok — her şeyi Telegram'dan
telefonundan yönetirsin.

## Akış (senin tarafın)
1. Telegram'a **görsel** gelir → **Onayla ✅** / **Farklı zemin 🎨** / **Atla ⏭️**
2. Onaylarsan **caption** gelir → **Yayınla 🚀** / **Düzelt ✏️** / **İptal ❌**
   (Düzeltmek için yeni caption'ı yazıp gönder.)
3. **Yayınla** dersen Instagram'a paylaşılır.
İstediğin an Telegram'a **`sonraki`** yazarak yeni kart isteyebilirsin.

## Tek seferlik kurulum

### 1. Telegram botu oluştur
- Telegram'da **@BotFather**'a yaz → `/newbot` → bir isim ver.
- Sana verdiği **bot token**'ı not et.

### 2. Kendi chat ID'ni öğren
- Telegram'da **@userinfobot**'a "merhaba" yaz; sana **numeric ID**'ni söyler.
- (Ya da yeni botuna bir mesaj at, sonra tarayıcıda
  `https://api.telegram.org/bot<TOKEN>/getUpdates` aç, `"chat":{"id":...}` değerini al.)
- Bir de yeni botuna Telegram'dan bir kez **"merhaba"** yaz (bot sana mesaj
  atabilsin diye sohbeti başlatman gerekiyor).

### 3. Secrets ekle
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- `TELEGRAM_BOT_TOKEN` = BotFather token'ı
- `TELEGRAM_CHAT_ID`  = senin numeric ID'n
- `IG_USER_ID` = `17841460149206261`  (zaten ekli)
- `IG_TOKEN`  = long-lived token     (zaten ekli)

### 4. Push + Actions
Bu dosyaları repona push et, **Actions**'ı aç. Repo **public** olmalı (Instagram
görseli oradan çekiyor). Hassas hiçbir şey dosyalarda değil; token'lar Secrets'ta.

## Otomatik çalışma
- `prepare.yml` — her gün 07:00 UTC (TR 10:00) bir kart hazırlayıp Telegram'a yollar.
- `poll.yml` — 10 dakikada bir senin dokunuşlarını işler; onayladığında yayınlar.
- `refresh.yml` — token'ı haftalık yeniler (GH_PAT eklersen otomatik; eklemezsen
  ~60 günde bir elle güncellersin).

Kart saatini değiştirmek için `prepare.yml` içindeki cron'u düzenle. GitHub'a
sadece bir kez (kurulum) girmen yeter; sonrası Telegram.

## Alıntı ekleme (`quotes.json`)
Her giriş gerçek kaynaktan, künyeli. `kaynak_dogrulandi: true` olmadan yayına
girmez. Yeni PDF/kaynak geldiğinde alıntıları birlikte formatlayıp ekleriz.
