import os
import re
import math
import time
import asyncio
import subprocess
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

try:
    from pyrogram import Client as PyroClient
    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False
    PyroClient = None

# ===== НАСТРОЙКИ =====
load_dotenv()
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise RuntimeError('Token not found. Add BOT_TOKEN to .env file')

DOWNLOAD_PATH = 'downloads'
MAX_FILE_SIZE = 50 * 1024 * 1024
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOUTUBE_COOKIES = os.path.join(_BASE_DIR, 'youtube_cookies.txt')
X_COOKIES = os.path.join(_BASE_DIR, 'x_cookies.txt')

os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# {chat_id: {'url': str, 'formats': list}}
user_data = {}

# {chat_id: 'ru'|'en'|'kz'|'uk'}
user_lang = {}

# Pyrogram client for large file uploads (>50 MB, up to 2 GB)
pyro_app = None

# ===== ПЕРЕВОДЫ =====
STRINGS = {
    'ru': {
        'welcome': (
            'Привет! Отправь мне ссылку на видео или публикацию '
            'с YouTube, Instagram, TikTok, Twitch или X (Twitter).\n\n'
            'Поддерживается: видео, длинные стримы, Reels, фото-посты, карусели Instagram.'
        ),
        'choose_lang': 'Выберите язык:',
        'lang_set': 'Язык изменён на Русский 🇷🇺',
        'send_link': 'Пожалуйста, отправь корректную ссылку (начинается с http:// или https://).',
        'unsupported_link': 'Ссылка не поддерживается. Отправь ссылку на видео из YouTube, Instagram, TikTok, Twitch или X (Twitter).',
        'getting_info': 'Получаю информацию...',
        'downloading': 'Скачиваю',
        'choose_quality': 'Выберите качество:',
        'auth_required': 'Этот контент требует авторизации. Попробуйте открытый пост.',
        'error': 'Ошибка: {}',
        'image_too_large': 'Изображение слишком большое ({:.1f} МБ).',
        'splitting': 'Файл {:.0f} МБ — разбиваю на {} части без потери качества...',
        'split_failed': 'Не удалось разбить видео.',
        'part': 'Часть {} из {}',
        'download_failed': 'Не удалось скачать медиа.',
        'instagram_failed': 'Не удалось скачать публикацию Instagram.',
        'instagram_error': 'Не удалось скачать публикацию: {}',
        'download_error': 'Ошибка при скачивании: {}',
        'session_expired': 'Информация устарела. Отправьте ссылку заново.',
        'mb_s': 'МБ/с',
        'kb_s': 'КБ/с',
        'of': 'из',
        'mb': 'МБ',
        'large_file_choice': 'Файл {:.0f} МБ — больше лимита Telegram (50 МБ). Что делать?',
        'btn_split': '✂️ Разбить на {} части',
        'btn_compress': '📉 Сжать (1 файл, хуже качество)',
        'compressing': 'Сжимаю видео...',
        'compress_failed': 'Не удалось сжать видео.',
        'uploading': 'Отправляю файл',
    },
    'en': {
        'welcome': (
            'Hello! Send me a link to a video or post '
            'from YouTube, Instagram, TikTok, Twitch, or X (Twitter).\n\n'
            'Supported: videos, long streams, Reels, photo posts, Instagram carousels.'
        ),
        'choose_lang': 'Choose language:',
        'lang_set': 'Language changed to English 🇬🇧',
        'send_link': 'Please send a valid link (starting with http:// or https://).',
        'unsupported_link': 'This link is not supported. Send a video link from YouTube, Instagram, TikTok, Twitch, or X (Twitter).',
        'getting_info': 'Getting info...',
        'downloading': 'Downloading',
        'choose_quality': 'Choose quality:',
        'auth_required': 'This content requires authorization. Try a public post.',
        'error': 'Error: {}',
        'image_too_large': 'Image is too large ({:.1f} MB).',
        'splitting': 'File is {:.0f} MB — splitting into {} parts without quality loss...',
        'split_failed': 'Failed to split video.',
        'part': 'Part {} of {}',
        'download_failed': 'Failed to download media.',
        'instagram_failed': 'Failed to download Instagram post.',
        'instagram_error': 'Failed to download post: {}',
        'download_error': 'Download error: {}',
        'session_expired': 'Session expired. Please send the link again.',
        'mb_s': 'MB/s',
        'kb_s': 'KB/s',
        'of': 'of',
        'mb': 'MB',
        'large_file_choice': 'File is {:.0f} MB — exceeds Telegram limit (50 MB). What to do?',
        'btn_split': '✂️ Split into {} parts',
        'btn_compress': '📉 Compress (1 file, lower quality)',
        'compressing': 'Compressing video...',
        'compress_failed': 'Failed to compress video.',
        'uploading': 'Uploading file',
    },
    'kz': {
        'welcome': (
            'Сәлем! Маған YouTube, Instagram, TikTok, Twitch немесе X (Twitter)-тен '
            'бейне немесе жарияланым сілтемесін жіберіңіз.\n\n'
            'Қолдау: бейнелер, ұзын стримдер, Reels, фото жарияланымдар, Instagram карусельдері.'
        ),
        'choose_lang': 'Тілді таңдаңыз:',
        'lang_set': 'Тіл Қазақшаға өзгертілді 🇰🇿',
        'send_link': 'Дұрыс сілтеме жіберіңіз (http:// немесе https:// басталатын).',
        'unsupported_link': 'Бұл сілтеме қолданылмайды. YouTube, Instagram, TikTok, Twitch немесе X (Twitter) бейне сілтемесін жіберіңіз.',
        'getting_info': 'Ақпарат алынуда...',
        'downloading': 'Жүктелуде',
        'choose_quality': 'Сапаны таңдаңыз:',
        'auth_required': 'Бұл мазмұн авторизацияны қажет етеді. Ашық жарияланымды көріңіз.',
        'error': 'Қате: {}',
        'image_too_large': 'Сурет тым үлкен ({:.1f} МБ).',
        'splitting': 'Файл {:.0f} МБ — {} бөлікке бөлінеді (сапа жоғалмайды)...',
        'split_failed': 'Бейнені бөлу мүмкін болмады.',
        'part': '{} / {} бөлік',
        'download_failed': 'Медиа жүктеу мүмкін болмады.',
        'instagram_failed': 'Instagram жарияланымын жүктеу мүмкін болмады.',
        'instagram_error': 'Жарияланымды жүктеу мүмкін болмады: {}',
        'download_error': 'Жүктеу қатесі: {}',
        'session_expired': 'Сессия мерзімі өтті. Сілтемені қайта жіберіңіз.',
        'mb_s': 'МБ/с',
        'kb_s': 'КБ/с',
        'of': '/',
        'mb': 'МБ',
        'large_file_choice': 'Файл {:.0f} МБ — Telegram лимитінен асады (50 МБ). Не істеу керек?',
        'btn_split': '✂️ {} бөлікке бөлу',
        'btn_compress': '📉 Сығу (1 файл, сапасы төмен)',
        'compressing': 'Бейне сығылуда...',
        'compress_failed': 'Бейнені сығу мүмкін болмады.',
        'uploading': 'Файл жүктеп салынуда',
    },
    'uk': {
        'welcome': (
            'Привіт! Надішли мені посилання на відео або публікацію '
            'з YouTube, Instagram, TikTok, Twitch або X (Twitter).\n\n'
            'Підтримується: відео, довгі стріми, Reels, фото-пости, каруселі Instagram.'
        ),
        'choose_lang': 'Оберіть мову:',
        'lang_set': 'Мову змінено на Українську 🇺🇦',
        'send_link': 'Будь ласка, надішли коректне посилання (починається з http:// або https://).',
        'unsupported_link': 'Це посилання не підтримується. Надішли посилання на відео з YouTube, Instagram, TikTok, Twitch або X (Twitter).',
        'getting_info': 'Отримую інформацію...',
        'downloading': 'Завантажую',
        'choose_quality': 'Оберіть якість:',
        'auth_required': 'Цей контент потребує авторизації. Спробуй відкритий пост.',
        'error': 'Помилка: {}',
        'image_too_large': 'Зображення занадто велике ({:.1f} МБ).',
        'splitting': 'Файл {:.0f} МБ — ділю на {} частини без втрати якості...',
        'split_failed': 'Не вдалося розбити відео.',
        'part': 'Частина {} з {}',
        'download_failed': 'Не вдалося завантажити медіа.',
        'instagram_failed': 'Не вдалося завантажити публікацію Instagram.',
        'instagram_error': 'Не вдалося завантажити публікацію: {}',
        'download_error': 'Помилка завантаження: {}',
        'session_expired': 'Інформація застаріла. Надішліть посилання знову.',
        'mb_s': 'МБ/с',
        'kb_s': 'КБ/с',
        'of': 'з',
        'mb': 'МБ',
        'large_file_choice': 'Файл {:.0f} МБ — перевищує ліміт Telegram (50 МБ). Що робити?',
        'btn_split': '✂️ Розбити на {} частини',
        'btn_compress': '📉 Стиснути (1 файл, гірша якість)',
        'compressing': 'Стискаю відео...',
        'compress_failed': 'Не вдалося стиснути відео.',
        'uploading': 'Вивантажую файл',
    },
}

LANG_BUTTONS = [
    ('🇷🇺 Русский', 'lang_ru'),
    ('🇬🇧 English', 'lang_en'),
    ('🇰🇿 Қазақша', 'lang_kz'),
    ('🇺🇦 Українська', 'lang_uk'),
]


def get_lang(chat_id: int) -> str:
    return user_lang.get(chat_id, 'ru')


def t(chat_id: int, key: str, *args) -> str:
    lang = get_lang(chat_id)
    template = STRINGS[lang].get(key, STRINGS['ru'].get(key, key))
    return template.format(*args) if args else template


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def is_valid_url(text: str) -> bool:
    return text.startswith(('http://', 'https://')) and '.' in text


def is_instagram_url(url: str) -> bool:
    return 'instagram.com' in url


def is_twitter_url(url: str) -> bool:
    return 'twitter.com' in url or 'x.com' in url or 't.co' in url


def get_instagram_shortcode(url: str) -> str | None:
    match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
    return match.group(1) if match else None


def download_instagram_sync(url: str) -> list:
    import sys
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instagram_cookies.txt')

    venv_bin = os.path.dirname(sys.executable)
    gallery_dl_bin = os.path.join(venv_bin, 'gallery-dl')
    if not os.path.exists(gallery_dl_bin):
        gallery_dl_bin = 'gallery-dl'

    cmd = [gallery_dl_bin, '-D', DOWNLOAD_PATH]
    if os.path.exists(cookies_file):
        cmd.extend(['--cookies', cookies_file])
    cmd.append(url)

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        error_out = proc.stderr.strip() or proc.stdout.strip() or 'gallery-dl failed'
        raise Exception(error_out)

    results = []
    for line in proc.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        filepath = os.path.abspath(line)
        if os.path.exists(filepath):
            results.append({
                'filepath': filepath,
                'title': os.path.splitext(os.path.basename(filepath))[0][:80],
            })

    if not results:
        raise Exception('No files downloaded')

    return results


def split_video_sync(filepath: str, max_mb: float = 40) -> list[str]:
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
        capture_output=True, text=True
    )
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        return []

    filesize = os.path.getsize(filepath)
    # Используем 40 МБ как цель чтобы части не превышали лимит Telegram при VBR
    n_parts = math.ceil(filesize / (max_mb * 1024 * 1024))
    part_duration = duration / n_parts

    base = os.path.splitext(filepath)[0]
    parts = []
    for i in range(n_parts):
        out = f'{base}_part{i + 1}of{n_parts}.mp4'
        subprocess.run(
            ['ffmpeg', '-i', filepath,
             '-ss', str(i * part_duration), '-t', str(part_duration),
             '-map', '0',
             '-c', 'copy', '-y', out],
            capture_output=True
        )
        if os.path.exists(out):
            # Если часть всё равно больше 48 МБ — пропускаем (защита от VBR)
            if os.path.getsize(out) <= 48 * 1024 * 1024:
                parts.append(out)
            else:
                os.remove(out)
    return parts


def compress_video_sync(filepath: str, target_mb: float = 45) -> str | None:
    """Сжимает видео до target_mb МБ через расчёт целевого битрейта"""
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
        capture_output=True, text=True
    )
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        return None

    target_bits = target_mb * 1024 * 1024 * 8
    audio_bits = 128 * 1000 * duration
    video_bits = target_bits - audio_bits
    video_bitrate = max(int(video_bits / duration / 1000), 100)  # kbps

    output = os.path.splitext(filepath)[0] + '_compressed.mp4'
    result = subprocess.run(
        ['ffmpeg', '-i', filepath,
         '-c:v', 'libx264', '-preset', 'ultrafast',
         '-b:v', f'{video_bitrate}k',
         '-vf', 'scale=trunc(min(iw\\,1280)/2)*2:-2',
         '-threads', '2',
         '-c:a', 'aac', '-b:a', '128k',
         '-movflags', '+faststart',
         '-y', output],
        capture_output=True
    )
    if result.returncode == 0 and os.path.exists(output):
        return output
    return None


def get_video_codec(filepath: str) -> str:
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name',
         '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def transcode_to_h264_sync(filepath: str) -> str | None:
    codec = get_video_codec(filepath)
    if codec == 'h264':
        return None

    output = os.path.splitext(filepath)[0] + '_h264.mp4'
    result = subprocess.run(
        ['ffmpeg', '-i', filepath,
         '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
         '-vf', 'scale=trunc(min(iw\\,1280)/2)*2:-2',
         '-threads', '2',
         '-c:a', 'aac', '-b:a', '128k',
         '-movflags', '+faststart',
         '-y', output],
        capture_output=True
    )
    if result.returncode == 0 and os.path.exists(output):
        return output
    return None


def get_video_dimensions(filepath: str) -> tuple[int, int]:
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height',
         '-of', 'csv=p=0', filepath],
        capture_output=True, text=True
    )
    try:
        parts = result.stdout.strip().split(',')
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


async def init_pyrogram():
    global pyro_app
    if not PYROGRAM_AVAILABLE:
        return
    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')
    if not api_id or not api_hash:
        return
    try:
        pyro_app = PyroClient(
            'bot_session',
            api_id=int(api_id),
            api_hash=api_hash,
            bot_token=TOKEN,
        )
        await pyro_app.start()
        print('Pyrogram started — large file support enabled (up to 2 GB)')
    except Exception as e:
        print(f'Pyrogram init failed: {e}')
        pyro_app = None


async def shutdown_pyrogram():
    global pyro_app
    if pyro_app:
        try:
            await pyro_app.stop()
        except Exception:
            pass


async def pyro_send_large(chat_id: int, filepath: str, status_msg=None):
    """Send a file up to 2 GB via Pyrogram MTProto, with upload progress."""
    ext = os.path.splitext(filepath)[1].lower()
    w, h = get_video_dimensions(filepath) if ext not in IMAGE_EXTS else (0, 0)

    last_edit: list[float] = [0.0]

    async def on_progress(current: int, total: int):
        now = time.monotonic()
        if status_msg and total and now - last_edit[0] > 2.5:
            last_edit[0] = now
            try:
                percent = min(current / total * 100, 100)
                filled = int(10 * percent / 100)
                bar = '█' * filled + '░' * (10 - filled)
                mb_now = current / 1024 / 1024
                mb_total = total / 1024 / 1024
                await status_msg.edit_text(
                    t(chat_id, 'uploading') +
                    f'\n[{bar}] {percent:.0f}% ({mb_now:.0f}/{mb_total:.0f} {t(chat_id, "mb")})'
                )
            except Exception:
                pass

    if status_msg:
        try:
            await status_msg.edit_text(t(chat_id, 'uploading') + '...')
        except Exception:
            pass

    if ext in IMAGE_EXTS:
        await pyro_app.send_photo(chat_id, filepath, progress=on_progress)
    else:
        await pyro_app.send_video(
            chat_id, filepath,
            width=w or 0, height=h or 0,
            supports_streaming=True,
            progress=on_progress,
        )


def find_downloaded_file(ydl, entry: dict) -> str | None:
    filename = ydl.prepare_filename(entry)
    if os.path.exists(filename):
        return filename
    base = os.path.splitext(filename)[0]
    for f in os.listdir(DOWNLOAD_PATH):
        if f.startswith(os.path.basename(base)):
            return os.path.join(DOWNLOAD_PATH, f)
    return None


def download_media_sync(opts: dict, url: str) -> list:
    results = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

        entries = info.get('entries') if info.get('_type') == 'playlist' else [info]
        if not entries:
            entries = [info]

        for entry in entries:
            if not entry:
                continue
            filepath = find_downloaded_file(ydl, entry)
            if filepath and os.path.exists(filepath):
                results.append({
                    'filepath': filepath,
                    'title': entry.get('title') or info.get('title') or 'media',
                })

    return results


def get_formats_sync(opts: dict, url: str) -> dict:
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def deduplicate_formats(formats: list) -> list:
    best_by_height = {}
    for f in formats:
        height = f['height']
        existing = best_by_height.get(height)
        if not existing:
            best_by_height[height] = f
        else:
            if f['ext'] == 'mp4' and existing['ext'] != 'mp4':
                best_by_height[height] = f
            elif (f.get('filesize') or 0) > (existing.get('filesize') or 0):
                best_by_height[height] = f
    return sorted(best_by_height.values(), key=lambda x: x['height'], reverse=True)


def make_progress_hook(state: dict):
    def hook(d):
        if d['status'] == 'downloading':
            state['downloaded'] = d.get('downloaded_bytes', 0)
            state['total'] = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            state['speed'] = d.get('speed') or 0
        elif d['status'] == 'finished':
            state['downloaded'] = state.get('total', 0)
    return hook


async def animate_progress(chat_id: int, msg, context: ContextTypes.DEFAULT_TYPE,
                           text: str, stop_event: asyncio.Event, state: dict = None):
    i = 0
    while not stop_event.is_set():
        try:
            await context.bot.send_chat_action(chat_id, 'upload_video')

            if state and state.get('total'):
                downloaded = state.get('downloaded', 0)
                total = state['total']
                speed = state.get('speed', 0)
                percent = min(downloaded / total * 100, 100)

                filled = int(10 * percent / 100)
                bar = '█' * filled + '░' * (10 - filled)

                speed_str = ''
                if speed > 1024 * 1024:
                    speed_str = f' • {speed / 1024 / 1024:.1f} {t(chat_id, "mb_s")}'
                elif speed > 0:
                    speed_str = f' • {speed / 1024:.0f} {t(chat_id, "kb_s")}'

                mb_label = t(chat_id, 'mb')
                of_label = t(chat_id, 'of')
                line = f'{text}\n[{bar}] {percent:.0f}% {of_label} {total / 1024 / 1024:.0f} {mb_label}{speed_str}'
            else:
                dots = ['.', '..', '...', '..']
                line = text + dots[i % 4]
                i += 1

            await msg.edit_text(line)
        except Exception:
            pass
        await asyncio.sleep(1.5)


async def send_file(chat_id: int, filepath: str, title: str, context: ContextTypes.DEFAULT_TYPE):
    part_paths = []
    try:
        filesize = os.path.getsize(filepath)
        ext = os.path.splitext(filepath)[1].lower()

        if filesize > MAX_FILE_SIZE:
            if ext in IMAGE_EXTS:
                await context.bot.send_message(
                    chat_id, t(chat_id, 'image_too_large', filesize / 1024 / 1024)
                )
                return

            n_parts = math.ceil(filesize / (40 * 1024 * 1024))
            await context.bot.send_message(
                chat_id,
                t(chat_id, 'splitting', filesize / 1024 / 1024, n_parts)
            )

            loop = asyncio.get_running_loop()
            part_paths = await loop.run_in_executor(None, split_video_sync, filepath)

            if not part_paths:
                await context.bot.send_message(chat_id, t(chat_id, 'split_failed'))
                return

            w, h = get_video_dimensions(filepath)
            for i, part in enumerate(part_paths, 1):
                with open(part, 'rb') as f:
                    await context.bot.send_video(
                        chat_id, video=f, supports_streaming=True,
                        width=w or None, height=h or None,
                        caption=t(chat_id, 'part', i, len(part_paths))
                    )
            return

        transcoded_path = None
        try:
            with open(filepath, 'rb') as f:
                if ext in IMAGE_EXTS:
                    await context.bot.send_photo(chat_id, photo=f)
                else:
                    loop = asyncio.get_running_loop()
                    transcoded_path = await loop.run_in_executor(
                        None, transcode_to_h264_sync, filepath
                    )
                    send_path = transcoded_path if transcoded_path else filepath
                    send_size = os.path.getsize(send_path)
                    if send_size > MAX_FILE_SIZE:
                        if pyro_app and send_size <= 2 * 1024 * 1024 * 1024:
                            await pyro_send_large(chat_id, send_path, None)
                            return
                        else:
                            n_parts = math.ceil(send_size / (40 * 1024 * 1024))
                            await context.bot.send_message(
                                chat_id, t(chat_id, 'splitting', send_size / 1024 / 1024, n_parts)
                            )
                            split_parts = await loop.run_in_executor(None, split_video_sync, send_path)
                            if not split_parts:
                                await context.bot.send_message(chat_id, t(chat_id, 'split_failed'))
                                return
                            w, h = get_video_dimensions(send_path)
                            for i, part in enumerate(split_parts, 1):
                                with open(part, 'rb') as pf:
                                    await context.bot.send_video(
                                        chat_id, video=pf, supports_streaming=True,
                                        width=w or None, height=h or None,
                                        caption=t(chat_id, 'part', i, len(split_parts))
                                    )
                                os.remove(part)
                            return
                    w, h = get_video_dimensions(send_path)
                    with open(send_path, 'rb') as vf:
                        await context.bot.send_video(
                            chat_id, video=vf, supports_streaming=True,
                            width=w or None, height=h or None
                        )
        finally:
            if transcoded_path and os.path.exists(transcoded_path):
                os.remove(transcoded_path)

    finally:
        for p in part_paths:
            if os.path.exists(p):
                os.remove(p)


async def download_and_send(url: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                            format_id: str = None, status_msg=None):
    downloaded_paths = []
    stop_event = asyncio.Event()
    progress_task = None
    progress_state = {}
    if status_msg:
        progress_task = asyncio.create_task(
            animate_progress(
                chat_id, status_msg, context,
                t(chat_id, 'downloading'), stop_event, progress_state
            )
        )
    try:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_PATH, f'{chat_id}_%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'format': f'{format_id}+bestaudio/bestaudio/best' if format_id else 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'progress_hooks': [make_progress_hook(progress_state)],
            'js_runtimes': {'node': {}},
        }
        if is_twitter_url(url) and os.path.exists(X_COOKIES):
            ydl_opts['cookiefile'] = X_COOKIES
        elif os.path.exists(YOUTUBE_COOKIES):
            ydl_opts['cookiefile'] = YOUTUBE_COOKIES

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, download_media_sync, ydl_opts, url)

        if not results:
            await context.bot.send_message(chat_id, t(chat_id, 'download_failed'))
            return

        for result in results:
            filepath = result['filepath']
            filesize = os.path.getsize(filepath)
            ext = os.path.splitext(filepath)[1].lower()

            PYRO_MAX = 2000 * 1024 * 1024  # 2000 MiB — жёсткий лимит Telegram MTProto
            if filesize > MAX_FILE_SIZE and ext not in IMAGE_EXTS:
                if pyro_app and filesize <= PYRO_MAX:
                    # Отправляем напрямую через Pyrogram (до 2000 МБ)
                    stop_event.set()
                    if progress_task and not progress_task.done():
                        progress_task.cancel()
                        try:
                            await progress_task
                        except (asyncio.CancelledError, Exception):
                            pass
                    downloaded_paths.append(filepath)
                    await pyro_send_large(chat_id, filepath, status_msg)
                else:
                    # Спрашиваем пользователя что делать с большим файлом
                    n_parts = math.ceil(filesize / (40 * 1024 * 1024))
                    user_data.setdefault(chat_id, {})['pending_large'] = {
                        'filepath': filepath,
                        'title': result['title'],
                    }
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            t(chat_id, 'btn_split', n_parts), callback_data='act_split'
                        )],
                        [InlineKeyboardButton(
                            t(chat_id, 'btn_compress'), callback_data='act_compress'
                        )],
                    ])
                    await context.bot.send_message(
                        chat_id,
                        t(chat_id, 'large_file_choice', filesize / 1024 / 1024),
                        reply_markup=keyboard
                    )
                    # Файл не удаляем — он нужен для обработки по кнопке
            else:
                downloaded_paths.append(filepath)
                await send_file(chat_id, filepath, result['title'], context)

    except yt_dlp.utils.DownloadError as e:
        err = str(e).lower()
        if 'no video' in err or 'there is no video' in err:
            try:
                loop = asyncio.get_running_loop()
                results = await loop.run_in_executor(None, download_instagram_sync, url)
                if not results:
                    await context.bot.send_message(chat_id, t(chat_id, 'instagram_failed'))
                    return
                downloaded_paths = [r['filepath'] for r in results]
                for result in results:
                    await send_file(chat_id, result['filepath'], result['title'], context)
            except Exception as ie:
                await context.bot.send_message(chat_id, t(chat_id, 'instagram_error', ie))
        elif 'requested format is not available' in err and format_id:
            # Выбранный формат недоступен — скачиваем лучший доступный
            await download_and_send(url, chat_id, context, format_id=None, status_msg=status_msg)
        elif 'unsupported url' in err or 'no suitable extractor' in err or 'unable to extract' in err:
            await context.bot.send_message(chat_id, t(chat_id, 'unsupported_link'))
        else:
            await context.bot.send_message(chat_id, t(chat_id, 'download_error', e))
    except Exception as e:
        await context.bot.send_message(chat_id, t(chat_id, 'download_error', e))
    finally:
        stop_event.set()
        if progress_task and not progress_task.done():
            progress_task.cancel()
        for path in downloaded_paths:
            if path and os.path.exists(path):
                os.remove(path)


# ===== ОБРАБОТЧИКИ =====
def language_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in LANG_BUTTONS]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        t(chat_id, 'choose_lang'),
        reply_markup=language_keyboard()
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        t(chat_id, 'choose_lang'),
        reply_markup=language_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id

    if not is_valid_url(url):
        await update.message.reply_text(t(chat_id, 'send_link'))
        return

    status_msg = await update.message.reply_text(t(chat_id, 'getting_info'))

    # Instagram — сразу через instaloader, минуя yt-dlp (избегаем 429)
    if is_instagram_url(url):
        await status_msg.edit_text(t(chat_id, 'downloading'))
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(None, download_instagram_sync, url)
            if results:
                for result in results:
                    await send_file(chat_id, result['filepath'], result['title'], context)
                for result in results:
                    if result['filepath'] and os.path.exists(result['filepath']):
                        os.remove(result['filepath'])
            else:
                await status_msg.edit_text(t(chat_id, 'instagram_failed'))
        except Exception as e:
            await status_msg.edit_text(t(chat_id, 'instagram_error', e))
        return

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'js_runtimes': {'node': {}},
        }
        if is_twitter_url(url) and os.path.exists(X_COOKIES):
            ydl_opts['cookiefile'] = X_COOKIES
        elif os.path.exists(YOUTUBE_COOKIES):
            ydl_opts['cookiefile'] = YOUTUBE_COOKIES
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_formats_sync, ydl_opts, url)
        formats = info.get('formats', [])

        video_formats = [
            {
                'format_id': f['format_id'],
                'height': f.get('height'),
                'fps': f.get('fps'),
                'ext': f.get('ext', 'N/A'),
                'filesize': f.get('filesize') or 0,
            }
            for f in formats
            if f.get('vcodec') != 'none' and f.get('height') is not None
        ]

        if not video_formats:
            await status_msg.edit_text(t(chat_id, 'downloading'))
            await download_and_send(url, chat_id, context, status_msg=status_msg)
            return

        video_formats = deduplicate_formats(video_formats)
        PYRO_MAX_MB = 2000 * 1024 * 1024
        video_formats = [
            f for f in video_formats
            if not f['filesize'] or f['filesize'] <= PYRO_MAX_MB
        ]
        user_data[chat_id] = {'url': url, 'formats': video_formats}

        keyboard = []
        mb_label = t(chat_id, 'mb')
        for f in video_formats:
            label = f"{f['height']}p"
            if f.get('fps') and f['fps'] > 30:
                label += f" {int(f['fps'])}fps"
            label += f" ({f['ext']})"
            if f['filesize']:
                label += f" ~{f['filesize'] / 1024 / 1024:.0f} {mb_label}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f['format_id'])])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await status_msg.edit_text(t(chat_id, 'choose_quality'), reply_markup=reply_markup)

    except yt_dlp.utils.DownloadError as e:
        err = str(e).lower()
        if 'no video' in err or 'there is no video' in err or 'requested format' in err or 'only images' in err:
            await status_msg.edit_text(t(chat_id, 'downloading'))
            await download_and_send(url, chat_id, context, status_msg=status_msg)
        elif 'login' in err or 'sign in' in err:
            await status_msg.edit_text(t(chat_id, 'auth_required'))
        elif 'unsupported url' in err or 'no suitable extractor' in err or 'unable to extract' in err:
            await status_msg.edit_text(t(chat_id, 'unsupported_link'))
        else:
            await status_msg.edit_text(t(chat_id, 'error', e))
    except Exception as e:
        await status_msg.edit_text(t(chat_id, 'error', e))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data

    # Выбор языка
    if data.startswith('lang_'):
        lang_code = data[5:]  # 'ru', 'en', 'kz', 'uk'
        if lang_code in STRINGS:
            user_lang[chat_id] = lang_code
            await query.edit_message_text(
                t(chat_id, 'lang_set') + '\n\n' + t(chat_id, 'welcome')
            )
        return

    # Действие с большим файлом
    if data in ('act_split', 'act_compress'):
        pending = (user_data.get(chat_id) or {}).pop('pending_large', None)
        if not pending or not os.path.exists(pending['filepath']):
            await query.edit_message_text(t(chat_id, 'session_expired'))
            return

        filepath = pending['filepath']
        loop = asyncio.get_running_loop()

        if data == 'act_split':
            filesize = os.path.getsize(filepath)
            n_parts = math.ceil(filesize / (40 * 1024 * 1024))
            await query.edit_message_text(
                t(chat_id, 'splitting', filesize / 1024 / 1024, n_parts)
            )
            part_paths = await loop.run_in_executor(None, split_video_sync, filepath)
            if not part_paths:
                await context.bot.send_message(chat_id, t(chat_id, 'split_failed'))
            else:
                w, h = get_video_dimensions(filepath)
                for i, part in enumerate(part_paths, 1):
                    with open(part, 'rb') as f:
                        await context.bot.send_video(
                            chat_id, video=f, supports_streaming=True,
                            width=w or None, height=h or None,
                            caption=t(chat_id, 'part', i, len(part_paths))
                        )
                    os.remove(part)

        else:  # act_compress
            await query.edit_message_text(t(chat_id, 'compressing'))
            compressed = await loop.run_in_executor(None, compress_video_sync, filepath)
            if not compressed:
                await context.bot.send_message(chat_id, t(chat_id, 'compress_failed'))
            else:
                w, h = get_video_dimensions(compressed)
                with open(compressed, 'rb') as f:
                    await context.bot.send_video(
                        chat_id, video=f, supports_streaming=True,
                        width=w or None, height=h or None
                    )
                os.remove(compressed)

        if os.path.exists(filepath):
            os.remove(filepath)
        return

    # Выбор качества видео
    if chat_id not in user_data or 'url' not in user_data.get(chat_id, {}):
        await query.edit_message_text(t(chat_id, 'session_expired'))
        return

    url = user_data[chat_id].pop('url')
    status_msg = await query.edit_message_text(t(chat_id, 'downloading'))
    await download_and_send(url, chat_id, context, format_id=data, status_msg=status_msg)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Unhandled error: {context.error}')


# ===== ЗАПУСК =====
async def post_init(_application: Application):
    await init_pyrogram()


async def post_shutdown(_application: Application):
    await shutdown_pyrogram()


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', language_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    print('Bot started...')
    app.run_polling()


if __name__ == '__main__':
    main()
