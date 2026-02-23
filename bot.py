import os
import re
import math
import asyncio
import subprocess
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp
import instaloader

# ===== НАСТРОЙКИ =====
load_dotenv()
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise RuntimeError('Token not found. Add BOT_TOKEN to .env file')

DOWNLOAD_PATH = 'downloads'
MAX_FILE_SIZE = 50 * 1024 * 1024
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}

os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# {chat_id: {'url': str, 'formats': list}}
user_data = {}

# {chat_id: 'ru'|'en'|'kz'|'uk'}
user_lang = {}

# ===== ПЕРЕВОДЫ =====
STRINGS = {
    'ru': {
        'welcome': (
            'Привет! Отправь мне ссылку на видео или публикацию '
            'с YouTube, Instagram или TikTok.\n\n'
            'Поддерживается: видео, Reels, фото-посты, карусели Instagram.'
        ),
        'choose_lang': 'Выберите язык:',
        'lang_set': 'Язык изменён на Русский 🇷🇺',
        'send_link': 'Пожалуйста, отправь корректную ссылку (начинается с http:// или https://).',
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
    },
    'en': {
        'welcome': (
            'Hello! Send me a link to a video or post '
            'from YouTube, Instagram, or TikTok.\n\n'
            'Supported: videos, Reels, photo posts, Instagram carousels.'
        ),
        'choose_lang': 'Choose language:',
        'lang_set': 'Language changed to English 🇬🇧',
        'send_link': 'Please send a valid link (starting with http:// or https://).',
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
    },
    'kz': {
        'welcome': (
            'Сәлем! Маған YouTube, Instagram немесе TikTok-тан '
            'бейне немесе жарияланым сілтемесін жіберіңіз.\n\n'
            'Қолдау: бейнелер, Reels, фото жарияланымдар, Instagram карусельдері.'
        ),
        'choose_lang': 'Тілді таңдаңыз:',
        'lang_set': 'Тіл Қазақшаға өзгертілді 🇰🇿',
        'send_link': 'Дұрыс сілтеме жіберіңіз (http:// немесе https:// басталатын).',
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
    },
    'uk': {
        'welcome': (
            'Привіт! Надішли мені посилання на відео або публікацію '
            'з YouTube, Instagram або TikTok.\n\n'
            'Підтримується: відео, Reels, фото-пости, каруселі Instagram.'
        ),
        'choose_lang': 'Оберіть мову:',
        'lang_set': 'Мову змінено на Українську 🇺🇦',
        'send_link': 'Будь ласка, надішли коректне посилання (починається з http:// або https://).',
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


def get_instagram_shortcode(url: str) -> str | None:
    match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
    return match.group(1) if match else None


def download_instagram_sync(url: str) -> list:
    shortcode = get_instagram_shortcode(url)
    if not shortcode:
        return []

    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        dirname_pattern=DOWNLOAD_PATH,
        filename_pattern=shortcode + '_{mediaid}',
    )

    ig_user = os.environ.get('INSTAGRAM_USER')
    ig_pass = os.environ.get('INSTAGRAM_PASS')
    if ig_user and ig_pass:
        try:
            L.login(ig_user, ig_pass)
        except Exception:
            pass

    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=DOWNLOAD_PATH)

    title = (post.caption or shortcode)[:80].strip()
    results = []

    for fname in os.listdir(DOWNLOAD_PATH):
        if fname.startswith(shortcode) and not fname.endswith(('.txt', '.json', '.xz')):
            results.append({
                'filepath': os.path.join(DOWNLOAD_PATH, fname),
                'title': title,
            })

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
         '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
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
            'outtmpl': os.path.join(DOWNLOAD_PATH, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'format': f'{format_id}+bestaudio[ext=m4a]/bestaudio/best' if format_id else 'bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'progress_hooks': [make_progress_hook(progress_state)],
        }

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, download_media_sync, ydl_opts, url)

        if not results:
            await context.bot.send_message(chat_id, t(chat_id, 'download_failed'))
            return

        downloaded_paths = [r['filepath'] for r in results]

        for result in results:
            await send_file(chat_id, result['filepath'], result['title'], context)

    except yt_dlp.utils.DownloadError as e:
        if 'no video' in str(e).lower() or 'there is no video' in str(e).lower():
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

    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
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
        err = str(e)
        if 'no video' in err.lower() or 'there is no video' in err.lower():
            await status_msg.edit_text(t(chat_id, 'downloading'))
            await download_and_send(url, chat_id, context, status_msg=status_msg)
        elif 'login' in err.lower() or 'sign in' in err.lower():
            await status_msg.edit_text(t(chat_id, 'auth_required'))
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

    # Выбор качества видео
    if chat_id not in user_data:
        await query.edit_message_text(t(chat_id, 'session_expired'))
        return

    url = user_data.pop(chat_id)['url']
    status_msg = await query.edit_message_text(t(chat_id, 'downloading'))
    await download_and_send(url, chat_id, context, format_id=data, status_msg=status_msg)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Unhandled error: {context.error}')


# ===== ЗАПУСК =====
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', language_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    print('Bot started...')
    app.run_polling()


if __name__ == '__main__':
    main()
