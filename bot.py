import asyncio
import logging
import re
import os  
import threading 
from flask import Flask 
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
# (!!!) ИСПРАВЛЕНИЕ: Мы ВОЗВРАЩАЕМ InputSticker
from aiogram.types import Message, InputSticker
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.bot import DefaultBotProperties 
from aiogram.fsm.storage.redis import RedisStorage

# --- Конфигурация ---
# Токен вставлен напрямую, как ты просил
BOT_TOKEN = "8094703198:AAFzaULimXczgidjUtPlyRTw6z_p-i0xavk"

# Ищем URL для Redis
REDIS_URL = os.environ.get("REDIS_URL")

if not BOT_TOKEN:
    logging.critical("Критическая ошибка: Токен BOT_TOKEN не найден.")
    exit()

if not REDIS_URL:
    logging.critical("Критическая ошибка: REDIS_URL не найден в переменных окружения.")
    exit("Ошибка: REDIS_URL не найден.")

# Создаем "память" для FSM
redis_storage = RedisStorage.from_url(REDIS_URL)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Используем DefaultBotProperties для указания parse_mode
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Передаем "память" в Dispatcher
dp = Dispatcher(storage=redis_storage)


# --- Машина состояний (FSM) ---
class CopyPack(StatesGroup):
    waiting_for_new_title = State()
    waiting_for_new_name = State()


# --- Обработчики (Хэндлеры) ---
# (cmd_start, handle_sticker, handle_link, get_new_title
# не изменились, они включены в код, листай ниже)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработчик команды /start
    """
    await message.answer(
        "Привет! 👋 Я бот для копирования стикерпаков.\n\n"
        "Отправь мне **любой стикер** из пака, который хочешь скопировать, "
        "или **ссылку** на пак (вида `t.me/addstickers/название`).\n\n"
        "Я создам для тебя полную копию этого пака, владельцем которой будешь ты."
    )

@dp.message(F.sticker)
async def handle_sticker(message: Message, state: FSMContext):
    """
    Ловит любой отправленный стикер.
    """
    if not message.sticker.set_name:
        await message.answer("У этого стикера нет 'set_name'. Кажется, это не часть пака, а кастомный стикер. Я не могу его скопировать.")
        return
    await state.update_data(original_set_name=message.sticker.set_name)
    await state.set_state(CopyPack.waiting_for_new_title)
    try:
        pack = await bot.get_sticker_set(message.sticker.set_name)
        pack_title = pack.title
    except Exception:
        pack_title = message.sticker.set_name
    await message.answer(
        f"Отлично, я вижу пак: <b>{pack_title}</b>\n\n"
        "Теперь придумай <b>новое название (Title)</b> для твоего будущего пака. Это то, что будет отображаться в списке стикеров."
    )

@dp.message(F.text.regexp(r"t\.me/addstickers/([a-zA-Z0-9_]+)"))
async def handle_link(message: Message, state: FSMContext):
    """
    Ловит ссылку на стикерпак.
    """
    original_set_name = re.search(r"t\.me/addstickers/([a-zA-Z0-9_]+)", message.text).group(1)
    if not original_set_name:
        await message.answer("Не смог распознать ссылку. Убедись, что она верная.")
        return
    await state.update_data(original_set_name=original_set_name)
    await state.set_state(CopyPack.waiting_for_new_title)
    try:
        pack = await bot.get_sticker_set(original_set_name)
        pack_title = pack.title
    except Exception:
        pack_title = original_set_name
    await message.answer(
        f"Отлично, я вижу пак: <b>{pack_title}</b>\n\n"
        "Теперь придумай <b>новое название (Title)</b> для твоего будущего пака. Это то, что будет отображаться в списке стикеров."
    )


@dp.message(CopyPack.waiting_for_new_title)
async def get_new_title(message: Message, state: FSMContext):
    """
    Получает новое название (Title) от пользователя.
    """
    me = await bot.get_me()
    bot_username = me.username
    await state.update_data(new_title=message.text)
    await state.set_state(CopyPack.waiting_for_new_name)
    await message.answer(
        f"Название принято: <b>{message.text}</b>\n\n"
        "Теперь придумай <b>новую ссылку (Short Name)</b>. Это уникальное имя пака.\n\n"
        "<b>Требования:</b>\n"
        "• Только латинские буквы (a-z), цифры (0-9) и '_'.\n"
        "• Должно быть уникальным (не занятым).\n"
        f"• Имя **должно** заканчиваться на `_by_{bot_username}` (юзернейм этого бота).\n\n"
        f"<b>Подсказка:</b> Можешь просто отправить имя пака (например, `Moi_Stikeri`), "
        f"и я **сам добавлю** `_by_{bot_username}` в конец."
    )


@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    """
    Получает новую ссылку (Short Name) и запускает процесс копирования.
    """
    user_data = await state.get_data()
    original_set_name = user_data.get("original_set_name")
    new_title = user_data.get("new_title")
    new_name = message.text.strip()
    user_id = message.from_user.id

    # --- Авто-добавление суффикса ---
    me = await bot.get_me()
    bot_suffix = f"_by_{me.username}" 
    
    if new_name.endswith(bot_suffix):
        pass 
    elif new_name.lower().endswith(bot_suffix.lower()):
        new_name = new_name[:-len(bot_suffix)]
        new_name = new_name + bot_suffix
        await message.answer(f"Я заметил ошибку в регистре суффикса. Исправляю имя на: <b>{new_name}</b>")
    else:
        new_name = new_name + bot_suffix
        await message.answer(f"Ты забыл суффикс. Автоматически добавляю его. Новое имя: <b>{new_name}</b>")
    
    msg = await message.answer(f"Принято. Начинаю процесс копирования для <b>{new_name}</b>... Это может занять несколько минут.")

    try:
        # 1. Получаем ИНФОРМАЦИЮ об оригинальном паке
        original_set = await bot.get_sticker_set(original_set_name)

        # 2. Определяем ТИП пака
        sticker_format = "static"
        if original_set.is_animated:
            sticker_format = "animated"
        elif original_set.is_video:
            sticker_format = "video"
        
        # --- (!!!) ИСПРАВЛЕНИЕ: Мы ВОЗВРАЩАЕМСЯ к InputSticker (!!!) ---
        stickers_to_add = []
        for sticker in original_set.stickers:
            
            current_emoji = sticker.emoji
            if not current_emoji:
                current_emoji = "🤩" # Эмодзи по умолчанию
            
            if not sticker.file_id:
                logging.warning(f"Стикер {sticker.file_unique_id} не имеет file_id, пропускаю.")
                continue
            
            # Мы снова создаем объекты InputSticker
            stickers_to_add.append(
                InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[current_emoji]
                )
            )

        if not stickers_to_add:
            await msg.edit_text("Не могу поверить, но в этом паке нет стикеров. Копирование отменено.")
            await state.clear()
            return
        
        # 4. Создаем НОВЫЙ пак
        await bot.create_new_sticker_set(
            user_id=user_id,
            name=new_name,
            title=new_title,
            stickers=[stickers_to_add[0]], # Передаем первый InputSticker
            sticker_format=sticker_format
        )
        
        # 5. Добавляем ОСТАЛЬНЫЕ стикеры
        if len(stickers_to_add) > 1:
            # --- (!!!) ГЛАВНОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ (!!!) ---
            # Раньше тут была ошибка, я передавал `stickers_to_add[i]`
            # Теперь я передаю сам объект 'sticker_obj' из цикла.
            for i, sticker_obj in enumerate(stickers_to_add[1:], start=1):
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    sticker=sticker_obj # <--- ВОТ ИСПРАВЛЕНИЕ
                )
                
                total_stickers = len(stickers_to_add)
                if i % 10 == 0 or (i+1) == total_stickers: 
                    await msg.edit_text(f"Копирую... {i+1}/{total_stickers}")
                
                await asyncio.sleep(0.1) 

        # 6. Готово!
        await msg.edit_text(
            f"✅ Успех! Я создал твой новый стикерпак.\n\n"
            f"Вот ссылка: t.me/addstickers/{new_name}"
        )

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text(f"❌ Ошибка. Имя (ссылка) `{new_name}` уже занято. Попробуй другое.")
            return 
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Ошибка. Оригинальный стикерпак не найден. Возможно, ссылка битая.")
        elif "USER_ID_INVALID" in str(e):
             await msg.edit_text("❌ Ошибка. Не могу найти твой ID. Странная ошибка.")
        else:
            await msg.edit_text(f"❌ Произошла неизвестная ошибка Telegram: {e}")
            logging.error(f"Ошибка при копировании: {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ Произошла критическая ошибка: {e}")
        logging.exception("Критическая ошибка в get_new_name_and_copy")

    finally:
        current_state = await state.get_state()
        if current_state is not None:
            await state.clear()


@dp.message()
async def handle_other_messages(message: Message):
    await message.answer("Я не понимаю. Пожалуйста, отправь мне стикер или ссылку на стикерпак.")


# --- БЛОК ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def i_am_alive():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080)) 
    app.run(host='0.0.0.0', port=port)

# --- Запуск Бота ---
async def main():
    logging.info("Бот запускается (через main)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Запуск Flask-потока...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logging.info("Запуск основного asyncio-бота...")
    asyncio.run(main())