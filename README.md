# SaveGlobalBot — Telegram Video Downloader Bot

Телеграм-бот для скачивания видео с YouTube, Instagram, TikTok, Twitch и других платформ. Работает на Hetzner VPS.

## Что умеет

- **YouTube** — скачивает видео с выбором качества, поддерживает длинные стримы
- **Instagram** — фото, видео, Reels, карусели (фото-посты)
- **TikTok** — видео
- **Twitch** и другие платформы через yt-dlp
- Файлы >50 МБ: предлагает разбить на части или сжать
- Файлы до 2 ГБ: отправляет через Pyrogram (MTProto)
- Мультиязычность: RU, EN, KZ, UK

---

## Сервер

- **Hetzner VPS**, Ubuntu 24.04
- Путь: `/opt/botdownloader/`
- Venv: `/opt/botdownloader/.venv/`
- Systemd сервис: `botdownloader`

```bash
# Статус
sudo systemctl status botdownloader

# Логи
journalctl -u botdownloader -n 50 --no-pager

# Перезапуск
sudo systemctl restart botdownloader

# Обновление
cd /opt/botdownloader && git pull && sudo systemctl restart botdownloader
```

---

## Файлы

| Файл | Назначение |
|------|-----------|
| `bot.py` | Основной код бота |
| `requirements.txt` | Python зависимости |
| `youtube_cookies.txt` | Куки YouTube (Netscape формат) |
| `instagram_cookies.txt` | Куки Instagram (для gallery-dl) |
| `.env` | `BOT_TOKEN`, `API_ID`, `API_HASH` (не в git) |
| `downloads/` | Временная папка для скачанных файлов |

---

## Зависимости

```
python-telegram-bot>=20.0   # Telegram Bot API
yt-dlp                      # Скачивание видео
yt-dlp[default]             # + yt-dlp-ejs (решение n-challenge для YouTube)
python-dotenv               # .env файл
instaloader                 # Instagram (fallback)
pyrogram                    # Отправка файлов >50 МБ
tgcrypto                    # Шифрование для Pyrogram
gallery-dl                  # Instagram (основной метод)
yt-dlp-youtube-oauth2       # OAuth2 для YouTube (установлен, но не используется активно)
```

---

## YouTube на Hetzner VPS — важные нюансы

### Проблема
Hetzner — датацентровый IP. YouTube блокирует/ограничивает скачивание с серверных IP.

### Решение (текущее)

1. **Node.js 22** установлен (`/usr/bin/node`) — нужен для решения n-challenge
2. **yt-dlp-ejs** — пакет с JavaScript-решателем для YouTube n-challenge
3. В коде бота: `'js_runtimes': {'node': {}}` в yt_dlp opts

   По умолчанию yt-dlp ждёт Deno (не установлен). Без этой настройки n-challenge не решается и скачиваются только превью (storyboards).

4. **Куки YouTube** (`youtube_cookies.txt`) — для контента требующего авторизацию

### Как работает скачивание

```
yt-dlp запрос → android_vr / web_safari клиенты → TV клиент (основной)
                                                         ↓
                                              Node.js решает n-challenge
                                                         ↓
                                              Скачивание по m3u8/https URL
```

### Ограничения

- Видео, которые YouTube помечает как требующие авторизации с серверных IP, могут не скачиваться даже с куками
- Куки нужно периодически обновлять (экспортировать из браузера расширением "Get cookies.txt LOCALLY")

### Обновление куков YouTube

1. В браузере установить расширение **Get cookies.txt LOCALLY**
2. Открыть youtube.com (залогиненный)
3. Экспортировать куки
4. Заменить `youtube_cookies.txt` в репозитории
5. `git pull && sudo systemctl restart botdownloader` на сервере

---

## Instagram на Hetzner VPS

Instagram блокирует yt-dlp с серверных IP (429 ошибки). Решение: используется **gallery-dl** с куками Instagram.

```python
# bot.py — функция download_instagram_sync
# Запускает: gallery-dl --cookies instagram_cookies.txt <url>
```

Куки Instagram (`instagram_cookies.txt`) тоже нужно периодически обновлять.

---

## .env файл (не в git)

```env
BOT_TOKEN=<токен от @BotFather>
API_ID=<Telegram API ID с my.telegram.org>
API_HASH=<Telegram API Hash с my.telegram.org>
PYRO_SESSION=bot_session
```

`API_ID` и `API_HASH` нужны для Pyrogram (отправка файлов >50 МБ).

---

## Установка с нуля

```bash
# Клонировать
git clone https://github.com/Bulldiga/SaveGlobalBot.git /opt/botdownloader
cd /opt/botdownloader

# Создать venv
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
pip install "yt-dlp[default]"        # устанавливает yt-dlp-ejs
pip install yt-dlp-youtube-oauth2

# Установить Node.js 22 (нужен для yt-dlp n-challenge)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt-get install -y nodejs

# Создать .env файл
cp .env.example .env  # или создать вручную

# Запустить через systemd
sudo systemctl enable botdownloader
sudo systemctl start botdownloader
```
