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
from aiogram.client.bot import DefaultBotProperties 
# (!!!) УБРАН: Импорт Redis (!!!)

BOT_TOKEN = "8094703198:AAFzaULimXczgidjUtPlyRTw6z_p-i0xavk"

# (!!!) УБРАНО: Подключение к Redis (!!!)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))

# (!!!) ИЗМЕНЕНО: Dispatcher теперь БЕЗ 'storage' (!!!)
# FSM будет "забывать" состояние после "сна"
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
    await message.answer(f"Придумай имя для нового пака (я добавлю _by_{me.username}_)")

@dp.message(F.text.regexp(r"t\.me/addstickers/([a-zA-Z0-9_]+)"))
async def handle_link(message: Message, state: FSMContext):
    original_set_name = re.search(r"t\.me/addstickers/([a-zA-Z0-9_]+)", message.text).group(1)
    
    await state.update_data(original_set_name=original_set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    me = await bot.get_me()
    await message.answer(f"Придумай имя для нового пака (я добавлю _by_{me.username}_)")

@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    user_data = await state.get_data()
    
    # (!!!) ВНИМАНИЕ: Эта проверка теперь КРИТИЧЕСКИ ВАЖНА (!!!)
    # Если бот "уснет", user_data будет пустым.
    if not user_data:
        await message.answer("Ой! Кажется, я 'заснул' и забыл, какой пак мы копируем. Начнем заново. Пожалуйста, отправь мне стикер еще раз.")
        await state.clear()
        return

    original_set_name = user_data.get("original_set_name")
    new_name = message.text.strip()
    user_id = message.from_user.id

    me = await bot.get_me()
    new_name = new_name + f"_by_{me.username}"
    
    msg = await message.answer("⏳ Начинаю копирование...")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        total_stickers = len(original_set.stickers)
        all_stickers = original_set.stickers
        
        # (!!!) ИСПРАВЛЕНИЕ: ПРАВИЛЬНОЕ определение формата (!!!)
        if original_set.is_video:
            main_format = "video"
        elif original_set.is_animated:
            main_format = "animated"
        else:
            main_format = "static"

        await msg.edit_text(f"🔄 Найден *{main_format}* пак ({total_stickers} стикеров).\nКопирую...")
        
        # ПАЧКА 1: создаем пак с первыми 50 стикерами
        first_batch = all_stickers[:50]
        first_batch_stickers = []
        
        for sticker in first_batch:
            # Копируем ТОЛЬКО стикеры нужного формата
            is_correct_format = (
                (main_format == "video" and sticker.is_video) or
                (main_format == "animated" and sticker.is_animated) or
                (main_format == "static" and not sticker.is_animated and not sticker.is_video)
            )

            if is_correct_format:
                emoji = sticker.emoji or "👍"
                first_batch_stickers.append(
                    InputSticker(
                        sticker=sticker.file_id,
                        emoji_list=[emoji],
                        format=main_format # Всегда используем ОДИН формат
                    )
                )

        if not first_batch_stickers:
            await msg.edit_text("❌ В этом паке нет стикеров нужного формата.")
            await state.clear()
            return

        # (!!!) Ловушка для флуд-контроля (!!!)
        try:
            await bot.create_new_sticker_set(
                user_id=user_id,
                name=new_name,
                title="ТГ Канал - @mupowkins",
                stickers=first_batch_stickers,
                sticker_format=main_format
            )
        except TelegramBadRequest as e:
            if "Flood control" in str(e) or "Too Many Requests" in str(e):
                match = re.search(r"retry after (\d+)", str(e))
                wait_time = int(match.group(1)) + 2 if match else 30
                await msg.edit_text(f"❗️ *Флуд-контроль на создании пака!*\nЖду {wait_time}с...")
                await asyncio.sleep(wait_time)
                await bot.create_new_sticker_set(
                    user_id=user_id,
                    name=new_name,
                    title="ТГ Канал - @mupowkins",
                    stickers=first_batch_stickers,
                    sticker_format=main_format
                )
            else:
                raise
        
        # Задержка 12 секунд
        await msg.edit_text(f"✅ Создан пак с первыми {len(first_batch_stickers)} стикерами.\nОжидание ~12 секунд...")
        await asyncio.sleep(12) 

        # Добавляем остальные стикеры пачками с задержкой 12 секунд
        if total_stickers > 50:
            remaining_stickers = all_stickers[50:]
            
            batch_size = 10
            for i in range(0, len(remaining_stickers), batch_size):
                batch = remaining_stickers[i:i + batch_size]
                
                for sticker in batch:
                    # Снова проверяем формат
                    is_correct_format = (
                        (main_format == "video" and sticker.is_video) or
                        (main_format == "animated" and sticker.is_animated) or
                        (main_format == "static" and not sticker.is_animated and not sticker.is_video)
                    )
                    
                    if is_correct_format:
                        emoji = sticker.emoji or "👍"
                        sticker_obj = InputSticker(
                            sticker=sticker.file_id,
                            emoji_list=[emoji],
                            format=main_format # Всегда ОДИН формат
                        )
                        
                        try:
                            await bot.add_sticker_to_set(
                                user_id=user_id,
                                name=new_name,
                                sticker=sticker_obj
                            )
                        except TelegramBadRequest as e:
                             if "Flood control" in str(e) or "Too Many Requests" in str(e):
                                await msg.edit_text(f"❗️ *Флуд-контроль на добавлении!*\nСплю 15с...")
                                await asyncio.sleep(15.0)
                                await bot.add_sticker_to_set(
                                    user_id=user_id,
                                    name=new_name,
                                    sticker=sticker_obj
                                )
                             else:
                                raise e
                
                current_progress = 50 + i + len(batch)
                
                if current_progress < total_stickers:
                    await msg.edit_text(f"✅ Добавлено {min(current_progress, total_stickers)}/{total_stickers}\nОжидание ~12 секунд...")
                    await asyncio.sleep(12) 

        await msg.edit_text(f"✅ Готово!\n*{main_format}* пак создан!\nt.me/addstickers/{new_name}\nСтикеров скопировано: {total_stickers}")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text("❌ Имя занято")
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Пак не найден")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ Слишком быстро! Подожди 30 секунд.")
        elif "STICKER_PNG_NOPNG" in str(e) or "STICKER_TGS_NOTGS" in str(e) or "STICKER_WEBM_NOWEBM" in str(e):
            await msg.edit_text("❌ Ошибка формата стикеров. Похоже, это 'сломанный' смешанный пак, который Телеграм не может обработать.")
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