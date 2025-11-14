import os
import re
import asyncio

from telegram import Update, InputSticker, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, AIORateLimiter

TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
PACK_SUFFIX = "_by_Mupowkins_BOT"
PACK_TITLE = "ТГ Канал - @Mupowkins"
MAX_STICKERS = 120

# Получение ссылки на новый стикерпак
def generate_new_pack_link(original_link):
    username = re.findall(r'addstickers/([A-Za-z0-9_]+)', original_link)
    if username:
        new_username = username[0] + PACK_SUFFIX
        return f'https://t.me/addstickers/{new_username}', new_username
    return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли мне ссылку на стикерпак или стикер для копирования.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    sticker = update.message.sticker

    if sticker:
        # Получение инфо о стикере
        sticker_set = await context.bot.get_sticker_set(sticker.set_name)
        await process_sticker_set(update, context, sticker_set)
    elif "addstickers" in text:
        match = re.search(r"(https://t.me/addstickers/S+)", text)
        if match:
            pack_url = match.group(1)
            # По ссылке получить имя сета
            set_name = pack_url.split("/")[-1]
            sticker_set = await context.bot.get_sticker_set(set_name)
            await process_sticker_set(update, context, sticker_set)
        else:
            await update.message.reply_text("Не распознал ссылку.")
    else:
        await update.message.reply_text("Пришли ссылку на стикерпак или стикер.")

async def process_sticker_set(update, context, sticker_set):
    # Генерация новой ссылки и имени
    new_link, new_name = generate_new_pack_link(f"https://t.me/addstickers/{sticker_set.name}")

    await update.message.reply_text(f"Создаю копию сета...
Новая ссылка будет: {new_link}")

    # Получаем список стикеров, не более MAX_STICKERS
    stickers = sticker_set.stickers[:MAX_STICKERS]
    new_stickers = []
    # Набор эмодзи для копирования (если их несколько — можно выбрать первые попавшиеся)
    for st in stickers:
        emoji = st.emoji or "🙂"
        if st.is_animated:
            f = await context.bot.get_file(st.file_id)
            f_path = await f.download_to_drive()
            new_stickers.append(InputSticker(sticker=InputFile(f_path), emoji_list=[emoji], type="animated"))
        elif st.is_video:
            f = await context.bot.get_file(st.file_id)
            f_path = await f.download_to_drive()
            new_stickers.append(InputSticker(sticker=InputFile(f_path), emoji_list=[emoji], type="video"))
        else:  # обычный .webp
            f = await context.bot.get_file(st.file_id)
            f_path = await f.download_to_drive()
            new_stickers.append(InputSticker(sticker=InputFile(f_path), emoji_list=[emoji], type="regular"))

    # Создаём новый стикер пак
    user_id = update.effective_user.id
    try:
        await context.bot.create_new_sticker_set(
            user_id=user_id,
            name=new_name,
            title=PACK_TITLE,
            stickers=new_stickers[:MAX_STICKERS]
        )
        await update.message.reply_text(f"Готово! Вот ссылка на новый пак: {new_link}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

def main():
    application = Application.builder().token(TG_TOKEN).rate_limiter(AIORateLimiter(1.5)).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT | filters.Sticker.ALL, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()