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
from aiogram.types import Message, InputSticker
from aiogram.exceptions import TelegramBadRequest

BOT_TOKEN = "8094703198:AAFzaULimXczgidjUtPlyRTw6z_p-i0xavk"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class CopyPack(StatesGroup):
    waiting_for_new_name = State()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Отправь стикер или ссылку на стикерпак")

@dp.message(F.sticker)
async def handle_sticker(message: Message, state: FSMContext):
    if not message.sticker.set_name:
        await message.answer("Этот стикер не из пака")
        return
    
    await state.update_data(original_set_name=message.sticker.set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    await message.answer(
        "📝 Придумай имя для стикерпака\n\n"
        "Я автоматически добавлю префикс 'Mupowkins_' в начало.\n"
        "Например, если введешь 'cats' - получится 'Mupowkins_cats'\n\n"
        "Введи имя:"
    )

@dp.message(F.text.regexp(r"t\.me/addstickers/([a-zA-Z0-9_]+)"))
async def handle_link(message: Message, state: FSMContext):
    original_set_name = re.search(r"t\.me/addstickers/([a-zA-Z0-9_]+)", message.text).group(1)
    
    await state.update_data(original_set_name=original_set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    await message.answer(
        "📝 Придумай имя для стикерпака\n\n"
        "Я автоматически добавлю префикс 'Mupowkins_' в начало.\n"
        "Например, если введешь 'cats' - получится 'Mupowkins_cats'\n\n"
        "Введи имя:"
    )

@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    user_data = await state.get_data()
    original_set_name = user_data.get("original_set_name")
    user_input_name = message.text.strip()
    user_id = message.from_user.id

    # Используем ПРЕФИКС вместо суффикса
    new_name = f"Mupowkins_{user_input_name}"
    
    msg = await message.answer("⏳ Начинаю копирование...")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        total_stickers = len(original_set.stickers)

        sticker_format = "static"
        if original_set.is_animated:
            sticker_format = "animated"
        elif original_set.is_video:
            sticker_format = "video"

        all_stickers = original_set.stickers
        
        # ПАЧКА 1: создаем пак с 50 стикерами
        await msg.edit_text("🔄 Создаю пак с первыми 50 стикерами...")
        first_batch = all_stickers[:50]
        first_batch_stickers = []
        
        for sticker in first_batch:
            emoji = sticker.emoji or "👍"
            first_batch_stickers.append(
                InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[emoji],
                    format=sticker_format
                )
            )

        await bot.create_new_sticker_set(
            user_id=user_id,
            name=new_name,
            title="ТГ Канал - @mupowkins",
            stickers=first_batch_stickers,
            sticker_format=sticker_format
        )

        await msg.edit_text("✅ Пак создан с 50 стикерами\n⏱️ Ожидаю 10 секунд...")
        await asyncio.sleep(10)

        # Добавляем остальные стикеры по одному с задержкой 1.1 секунды
        await msg.edit_text("🔄 Добавляю стикеры по одному... 50/120")
        
        for i, sticker in enumerate(all_stickers[50:], 51):
            emoji = sticker.emoji or "👍"
            
            sticker_obj = InputSticker(
                sticker=sticker.file_id,
                emoji_list=[emoji],
                format=sticker_format
            )
            
            await bot.add_sticker_to_set(
                user_id=user_id,
                name=new_name,
                sticker=sticker_obj
            )
            
            # Задержка 1.1 секунды между стикерами
            await asyncio.sleep(1.1)
            
            # Обновляем прогресс только каждые 10 стикеров
            if i % 10 == 0:
                await msg.edit_text(f"✅ Добавлено {i}/120")

        await msg.edit_text(f"✅ Готово!\nt.me/addstickers/{new_name}\nСтикеров: {total_stickers}")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text("❌ Имя занято")
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Пак не найден")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ Флуд-контроль! Попробуй через 2 минуты.")
        else:
            await msg.edit_text(f"❌ Ошибка: {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")

    await state.clear()

@dp.message()
async def handle_other_messages(message: Message):
    await message.answer("Отправь стикер или ссылку")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def run_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()