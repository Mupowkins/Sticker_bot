# file: sticker_copy_bot.py
import logging
import re
from io import BytesIO
from typing import Dict

from telegram import (
    Update,
    InputFile,
    MessageEntity,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- Настройка логов ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Хранилище состояния (простой dict для демонстрации) ----------
USER_STATE: Dict[int, dict] = {}
# STATE keys per user id:
# {
#   "step": "await_confirm" | "await_newname" | None,
#   "source_name": "<sticker_set_name>",
#   "stickers": [sticker objects from getStickerSet],
#   "title": "<original title>"
# }

# ---------- Помощники ----------
def ensure_bot_suffix(name: str, bot_username: str) -> str:
    """Гарантировать, что имя набора заканчивается на _by_<bot_username>"""
    if not name.endswith(f"_by_{bot_username}"):
        # удалить недопустимые символы и добавить суффикс
        base = re.sub(r'[^a-z0-9_]', '_', name.lower())
        return f"{base}_by_{bot_username}"
    return name

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для законного копирования ваших собственных стикерпаков.\n\n"
        "Отправь мне /copy <имя_набора> или просто пришли ссылку или стикер из набора.\n\n"
        "Важно: перед созданием нового набора ты должен подтвердить, что ты владеешь правами на стикеры."
    )

async def copy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Парсим аргумент — имя набора
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /copy <sticker_set_name> (например, FunnyCats_by_Author).")
        return

    source_name = args[0].strip()
    user_id = update.effective_user.id

    # Сохраняем состояние
    USER_STATE[user_id] = {"step": "await_confirm", "source_name": source_name}
    await update.message.reply_text(
        f"Вы хотите скопировать набор `{source_name}`.\n"
        "Пожалуйста, подтвердите, что вы являетесь владельцем стикеров или имеете разрешение.\n"
        "Отправьте сообщение: `I confirm I own these stickers` (буквально).",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    state = USER_STATE.get(user_id)
    if not state:
        await update.message.reply_text("Не понял. Отправь /copy <имя_набора> или пришли стикер из набора.")
        return

    if state.get("step") == "await_confirm":
        if text == "I confirm I own these stickers":
            source_name = state["source_name"]
            try:
                # получить набор
                stickerset = await context.bot.get_sticker_set(source_name)
            except Exception as e:
                logger.exception("getStickerSet failed")
                await update.message.reply_text(f"Не удалось получить набор `{source_name}`. Убедитесь, что имя правильное.", parse_mode="Markdown")
                USER_STATE.pop(user_id, None)
                return

            # сохраняем стикеры в состоянии
            state["stickers"] = stickerset.stickers
            state["title"] = stickerset.title
            state["step"] = "await_newname"

            await update.message.reply_text(
                f"Набор `{source_name}` успешно получен — в нём {len(stickerset.stickers)} стикеров.\n"
                "Теперь отправьте новое *название* для создаваемого набора (видимое название, например: My Cool Pack).",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("Подтверждение не распознано. Отправьте текст: `I confirm I own these stickers`.")
        return

    if state.get("step") == "await_newname":
        new_title = text[:64]  # ограничение длины заголовка
        state["new_title"] = new_title

        # предложим автоматическое машинное имя (endpoint) и уточним
        bot_user = await context.bot.get_me()
        suggested_name = ensure_bot_suffix(re.sub(r'\s+', '_', new_title), bot_user.username)

        state["step"] = "creating"
        await update.message.reply_text(f"Попробую создать новый набор с названием *{new_title}* и машин-именем `{suggested_name}`.\nЭто может занять время...", parse_mode="Markdown")

        # выполняем создание
        await create_new_pack_from_state(update, context, user_id, suggested_name)
        USER_STATE.pop(user_id, None)
        return

    # fallback
    await update.message.reply_text("Непонятный шаг. Начните снова: /copy <имя_набора>")

# ---------- Основная логика: скачивание + создание набора ----------
async def create_new_pack_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, new_pack_name: str):
    state = USER_STATE.get(user_id)
    if not state:
        await update.message.reply_text("Состояние не найдено — начните снова.")
        return

    stickers = state.get("stickers", [])
    if not stickers:
        await update.message.reply_text("В наборе нет стикеров или произошла ошибка.")
        return

    bot_username = (await context.bot.get_me()).username

    # проверка суффикса
    if not new_pack_name.endswith(f"_by_{bot_username}"):
        await update.message.reply_text(
            f"Имя набора должно заканчиваться на `_by_{bot_username}`. Попробуйте снова."
        )
        return

    # Первый стикер - для createNewStickerSet
    created = False
    errors = []
    new_title = state.get("new_title", "New Pack")
    for idx, st in enumerate(stickers):
        try:
            file = await context.bot.get_file(st.file_id)
            bio = BytesIO()
            await file.download_to_memory(out=bio)
            bio.seek(0)

            # Определяем тип стикера: is_animated, is_video, else static
            if getattr(st, "is_animated", False):
                input_file = InputFile(bio, filename="sticker.tgs")
                kwargs = {"tgs_sticker": input_file}
            elif getattr(st, "is_video", False):
                input_file = InputFile(bio, filename="sticker.webm")
                kwargs = {"webm_sticker": input_file}
            else:
                input_file = InputFile(bio, filename="sticker.png")
                kwargs = {"png_sticker": input_file}

            emojis = st.emojis if hasattr(st, "emojis") and st.emojis else "🙂"

            if not created:
                # create new set
                await context.bot.create_new_sticker_set(
                    user_id=user_id,
                    name=new_pack_name,
                    title=new_title,
                    emojis=emojis,
                    **kwargs
                )
                created = True
                logger.info("Created new sticker set %s", new_pack_name)
            else:
                # add sticker
                await context.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_pack_name,
                    emojis=emojis,
                    **kwargs
                )
            # небольшая пауза не требуется, библиотека асинхронная

        except Exception as e:
            logger.exception("Ошибка при обработке стикера")
            errors.append(f"index {idx}: {e}")

    if created and not errors:
        await update.message.reply_text(
            f"Готово! Новый набор создан: `{new_pack_name}`. Откройте t.me/addstickers/{new_pack_name}",
            parse_mode="Markdown"
        )
    elif created:
        await update.message.reply_text(
            f"Набор создан с частичными ошибками. Посмотри логи. errors: {errors}"
        )
    else:
        await update.message.reply_text(f"Не удалось создать набор. Ошибки: {errors}")

# ---------- Обработчик стикеров (если пользователь просто прислал стикер) ----------
async def sticker_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = update.message.sticker
    if not st:
        return

    # получаем имя набора, если есть
    if st.set_name:
        source_name = st.set_name
        user_id = update.effective_user.id
        USER_STATE[user_id] = {"step": "await_confirm", "source_name": source_name}
        await update.message.reply_text(
            f"Вы прислали стикер из набора `{source_name}`.\n"
            "Если вы хотите скопировать набор, подтвердите: `I confirm I own these stickers`.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Стикер не принадлежит набору или информация недоступна.")

# ---------- Регистрация и запуск ----------
def main():
    import os
    TOKEN = os.environ.get("TG_BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("Установите переменную окружения TG_BOT_TOKEN с вашим токеном бота.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("copy", copy_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_message))

    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()