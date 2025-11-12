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
    
    me = await bot.get_me()
    await message.answer(f"Придумай имя для нового пака (я добавлю _by_{me.username})")

@dp.message(F.text.regexp(r"t\.me/addstickers/([a-zA-Z0-9_]+)"))
async def handle_link(message: Message, state: FSMContext):
    original_set_name = re.search(r"t\.me/addstickers/([a-zA-Z0-9_]+)", message.text).group(1)
    
    await state.update_data(original_set_name=original_set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    me = await bot.get_me()
    await message.answer(f"Придумай имя для нового пака (я добавлю _by_{me.username})")

@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    user_data = await state.get_data()
    original_set_name = user_data.get("original_set_name")
    new_name = message.text.strip()
    user_id = message.from_user.id

    me = await bot.get_me()
    new_name = new_name + f"_by_{me.username}"
    
    msg = await message.answer("⏳ Начинаю копирование...")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        total_stickers = len(original_set.stickers)

        # Проверяем, есть ли смешанные форматы
        has_video = any(sticker.is_video for sticker in original_set.stickers)
        has_animated = any(sticker.is_animated for sticker in original_set.stickers)
        has_static = any(not sticker.is_video and not sticker.is_animated for sticker in original_set.stickers)

        # Определяем основной формат пака
        if has_video:
            sticker_format = "video"
            await msg.edit_text("🎥 Обнаружены видео стикеры...")
        elif has_animated:
            sticker_format = "animated"
            await msg.edit_text("🎬 Обнаружены анимированные стикеры...")
        else:
            sticker_format = "static"
            await msg.edit_text("📷 Обнаружены статичные стикеры...")

        # Если смешанные форматы - предупреждаем пользователя
        format_count = sum([has_video, has_animated, has_static])
        if format_count > 1:
            await msg.edit_text("⚠️ В паке смешанные форматы стикеров. Копирую только основной тип...")

        all_stickers = original_set.stickers
        
        # Фильтруем стикеры по основному формату
        if has_video:
            filtered_stickers = [sticker for sticker in all_stickers if sticker.is_video]
        elif has_animated:
            filtered_stickers = [sticker for sticker in all_stickers if sticker.is_animated]
        else:
            filtered_stickers = [sticker for sticker in all_stickers if not sticker.is_video and not sticker.is_animated]

        # Если после фильтрации стикеров нет - используем все
        if not filtered_stickers:
            filtered_stickers = all_stickers
            await msg.edit_text("⚠️ Не удалось определить формат, копирую все стикеры...")

        total_to_copy = len(filtered_stickers)
        
        # ПАЧКА 1: создаем пак с первыми 50 стикерами ОДНОГО ФОРМАТА
        await msg.edit_text(f"🔄 Создаю пак с первыми {min(50, total_to_copy)} стикерами...")
        first_batch = filtered_stickers[:50]
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

        await msg.edit_text(f"✅ Создан пак с первыми {len(first_batch)} стикерами\nОжидание ~10 секунд.")
        await asyncio.sleep(10)

        # Добавляем остальные стикеры ОДНОГО ФОРМАТА
        if total_to_copy > 50:
            remaining_stickers = filtered_stickers[50:]
            
            for i, sticker in enumerate(remaining_stickers, 51):
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
                
                # Обновляем прогресс каждые 10 стикеров
                if i % 10 == 0:
                    await msg.edit_text(f"✅ Добавлено {i}/{total_to_copy}")

        await msg.edit_text(f"✅ Готово!\nt.me/addstickers/{new_name}\nСтикеров: {total_to_copy}")

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