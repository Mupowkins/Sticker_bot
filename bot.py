import os
import threading
import http.server
import socketserver
import logging
import re
from io import BytesIO
from typing import Dict

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- Вспомогательная "заглушка" для Render ----------
def keep_alive():
    """Запуск простого HTTP сервера, чтобы Render не останавливал процесс."""
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"⚡ Keep-alive сервер запущен на порту {port}")
        httpd.serve_forever()

# Запускаем в отдельном потоке
threading.Thread(target=keep_alive, daemon=True).start()

# ---------- Настройка логов ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Глобальные состояния пользователей ----------
USER_STATE: Dict[int, dict] = {}

# ---------- Хелперы ----------
def ensure_bot_suffix(name: str, bot_username: str) -> str:
    """Гарантировать, что имя набора заканчивается на _by_<bot_username>"""
    if not name.endswith(f"_by_{bot_username}"):
        base = re.sub(r'[^a-z0-9_]', '_', name.lower())
        return f"{base}_by_{bot_username}"
    return name


# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для законного копирования твоих собственных стикерпаков.\n\n"
        "Отправь мне /copy <имя_набора> или просто пришли стикер из набора.\n\n"
        "⚠️ Перед копированием ты должен подтвердить, что обладаешь правами на стикеры."
    )


async def copy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /copy <sticker_set_name>")
        return

    source_name = args[0].strip()
    user_id = update.effective_user.id
    USER_STATE[user_id] = {"step": "await_confirm", "source_name": source_name}

    await update.message.reply_text(
        f"Ты хочешь скопировать набор `{source_name}`.\n"
        "Подтверди, что ты владелец: отправь сообщение `I confirm I own these stickers`.",
        parse_mode="Markdown"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = USER_STATE.get(user_id)

    if not state:
        await update.message.reply_text("Не понял. Отправь /copy <имя_набора> или стикер из набора.")
        return

    # --- Подтверждение ---
    if state.get("step") == "await_confirm":
        if text == "I confirm I own these stickers":
            source_name = state["source_name"]
            try:
                stickerset = await context.bot.get_sticker_set(source_name)
            except Exception as e:
                logger.exception("Ошибка getStickerSet")
                await update.message.reply_text(f"Не удалось получить набор `{source_name}`.", parse_mode="Markdown")
                USER_STATE.pop(user_id, None)
                return

            state["stickers"] = stickerset.stickers
            state["title"] = stickerset.title
            state["step"] = "await_newname"

            await update.message.reply_text(
                f"✅ Набор `{source_name}` получен — {len(stickerset.stickers)} стикеров.\n"
                "Теперь отправь новое *название* набора (например, My New Pack).",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("Отправь точный текст подтверждения: `I confirm I own these stickers`.")
        return

    # --- Получаем новое название ---
    if state.get("step") == "await_newname":
        new_title = text[:64]
        state["new_title"] = new_title

        bot_user = await context.bot.get_me()
        suggested_name = ensure_bot_suffix(re.sub(r'\s+', '_', new_title), bot_user.username)

        state["step"] = "creating"
        await update.message.reply_text(
            f"Создаю новый набор *{new_title}* с именем `{suggested_name}`...",
            parse_mode="Markdown"
        )

        await create_new_pack_from_state(update, context, user_id, suggested_name)
        USER_STATE.pop(user_id, None)
        return


# ---------- Логика создания нового набора ----------
async def create_new_pack_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, new_pack_name: str):
    state = USER_STATE.get(user_id)
    if not state:
        await update.message.reply_text("Ошибка состояния. Попробуй снова.")
        return

    stickers = state.get("stickers", [])
    if not stickers:
        await update.message.reply_text("В наборе нет стикеров.")
        return

    bot_username = (await context.bot.get_me()).username
    if not new_pack_name.endswith(f"_by_{bot_username}"):
        await update.message.reply_text(f"Имя должно заканчиваться на `_by_{bot_username}`.")
        return

    created = False
    errors = []
    new_title = state.get("new_title", "New Pack")

    for idx, st in enumerate(stickers):
        try:
            file = await context.bot.get_file(st.file_id)
            bio = BytesIO()
            await file.download_to_memory(out=bio)
            bio.seek(0)

            if getattr(st, "is_animated", False):
                kwargs = {"tgs_sticker": InputFile(bio, filename="sticker.tgs")}
            elif getattr(st, "is_video", False):
                kwargs = {"webm_sticker": InputFile(bio, filename="sticker.webm")}
            else:
                kwargs = {"png_sticker": InputFile(bio, filename="sticker.png")}

            emojis = st.emojis or "🙂"

            if not created:
                await context.bot.create_new_sticker_set(
                    user_id=user_id,
                    name=new_pack_name,
                    title=new_title,
                    emojis=emojis,
                    **kwargs
                )
                created = True
            else:
                await context.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_pack_name,
                    emojis=emojis,
                    **kwargs
                )

        except Exception as e:
            logger.exception("Ошибка при добавлении стикера")
            errors.append(f"{idx}: {e}")

    if created:
        url = f"https://t.me/addstickers/{new_pack_name}"
        await update.message.reply_text(f"🎉 Готово! Новый набор: [Открыть]({url})", parse_mode="Markdown")
    else:
        await update.message.reply_text("Не удалось создать набор. Проверь логи Render.")


# ---------- Обработка стикеров ----------
async def sticker_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = update.message.sticker
    if not st:
        return

    if st.set_name:
        user_id = update.effective_user.id
        USER_STATE[user_id] = {"step": "await_confirm", "source_name": st.set_name}
        await update.message.reply_text(
            f"Ты прислал стикер из `{st.set_name}`.\n"
            "Чтобы скопировать набор, отправь `I confirm I own these stickers`.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Этот стикер не связан с набором.")


# ---------- Основная функция ----------
def main():
    TOKEN = os.environ.get("TG_BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("Установи переменную окружения TG_BOT_TOKEN с токеном бота.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("copy", copy_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_message))

    logger.info("🤖 Бот запущен (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
