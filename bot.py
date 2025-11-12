import asyncio
import logging
import re
import os  
import threading 
import random
from flask import Flask 
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InputSticker
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.bot import DefaultBotProperties

BOT_TOKEN = "8094703198:AAFzaULimXczgidjUtPlyRTw6z_p-i0xavk"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class CopyPack(StatesGroup):
    waiting_for_new_name = State()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Отправь стикер или ссылку на стикерпак")

@dp.message(F.sticker)
async def handle_sticker(message: Message, state: FSMContext):
    if not message.sticker.set_name:
        await message.answer("Этот стикер не из пака")
        return
    
    await state.update_data(original_set_name=message.sticker.set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    me = await bot.get_me()
    await message.answer(f"Придумай имя для нового пака (я автоматически добавлю <b>_by_{me.username}</b>)")

@dp.message(F.text.regexp(r"t\.me/addstickers/([a-zA-Z0-9_]+)"))
async def handle_link(message: Message, state: FSMContext):
    original_set_name = re.search(r"t\.me/addstickers/([a-zA-Z0-9_]+)", message.text).group(1)
    
    await state.update_data(original_set_name=original_set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    me = await bot.get_me()
    await message.answer(f"Придумай имя для нового пака (я автоматически добавлю <b>_by_{me.username}</b>)")

@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    user_data = await state.get_data()

    # --- Проверка на "амнезию" (если бот "уснул") ---
    if not user_data:
        await message.answer("Ой! Кажется, я 'заснул' и забыл, какой пак мы копируем. Начнем заново. Пожалуйста, отправь мне стикер еще раз.")
        await state.clear()
        return
    # ---
    
    original_set_name = user_data.get("original_set_name")
    new_name = message.text.strip()
    user_id = message.from_user.id

    me = await bot.get_me()
    new_name = new_name + f"_by_{me.username}"
    
    msg = await message.answer("⏳ <b>Начинаю копирование...</b>\nОпределяю тип пака...")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        total_stickers = len(original_set.stickers)
        all_stickers = original_set.stickers

        sticker_format = "static"
        if original_set.is_animated:
            sticker_format = "animated"
        elif original_set.is_video:
            sticker_format = "video"

        # --- (!!!) НОВАЯ ЛОГИКА (1-50, затем 1с/стикер) (!!!) ---

        # 1. Определяем МАКС. РАЗМЕР ПЕРВОЙ ПАЧКИ
        # (Пользовательское правило: 1-50)
        max_initial_batch_size = 50

        # 2. Функция-помощник для конвертации
        def convert_sticker(sticker):
            if not sticker.file_id:
                return None
            return InputSticker(
                sticker=sticker.file_id,
                emoji_list=["🤩"], # Все стикеры с 🤩
                format=sticker_format # Поле format ОБЯЗАТЕЛЬНО
            )

        # 3. ПАЧКА 1: (1-50 стикеров)
        initial_batch_size = min(max_initial_batch_size, total_stickers)
        batch_1_objects = [convert_sticker(s) for s in all_stickers[:initial_batch_size] if s and s.file_id]
        
        if not batch_1_objects:
            await msg.edit_text("❌ В этом паке нет стикеров.")
            await state.clear()
            return

        # Создаем пак ОДНИМ ЗАПРОСОМ
        await msg.edit_text(f"⏳ Создаю пак с первыми {len(batch_1_objects)} стикерами...")
        await bot.create_new_sticker_set(
            user_id=user_id,
            name=new_name,
            title="ТГ Канал - @mupowkins",
            stickers=batch_1_objects, # Передаем всю пачку
            sticker_format=sticker_format
        )
        
        current_total_added = len(batch_1_objects)
        
        # 4. Проверяем, нужно ли добавлять ОСТАТОК
        if total_stickers <= current_total_added:
            await msg.edit_text(f"✅ <b>Готово!</b>\nПак скопирован: t.me/addstickers/{new_name}\nВсего стикеров: {total_stickers}")
            await state.clear()
            return

        # 5. ПАЧКА 2: (Остаток, 51+) - 10 стикеров в 10 секунд (1с/стикер)
        
        remaining_stickers = all_stickers[current_total_added:]
        
        await msg.edit_text(f"✅ Добавлено {current_total_added}/{total_stickers}.\nДобавляю оставшиеся {len(remaining_stickers)} (по 1 в 1.0с)...")
        
        for i, sticker in enumerate(remaining_stickers):
            
            sticker_obj = convert_sticker(sticker)
            if not sticker_obj:
                continue 

            try:
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    sticker=sticker_obj
                )
            except TelegramBadRequest as e:
                if "Flood control" in str(e) or "Too Many Requests" in str(e):
                    await msg.edit_text(f"❗️ Флуд-контроль! (на {current_total_added+1}-м стикере)\nСплю 15с и пробую снова...")
                    await asyncio.sleep(15.0)
                    await bot.add_sticker_to_set(
                        user_id=user_id,
                        name=new_name,
                        sticker=sticker_obj
                    )
                else:
                    raise e 
            
            current_total_added = i + 1 + initial_batch_size
            
            # --- Обновление прогресса ---
            if current_total_added % 10 == 0: 
                await msg.edit_text(f"⏳ Добавлено {current_total_added}/{total_stickers} стикеров...")

            # (!!!) НОВАЯ ЗАДЕРЖКА (!!!)
            # 10 стикеров в 10 секунд = 1 стикер в 1 секунду
            await asyncio.sleep(1.0)

        # --- Конец цикла ---
        await msg.edit_text(f"✅ <b>Готово!</b>\nПак скопирован: t.me/addstickers/{new_name}\nВсего стикеров: {total_stickers}")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text(f"❌ <b>Ошибка:</b> Имя <code>{new_name}</code> уже занято. Попробуй другое.")
            return 
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ <b>Ошибка:</b> Пак не найден. Возможно, ссылка битая.")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ <b>Слишком много запросов!</b>\nТелеграм временно ограничил бота. Пожалуйста, попробуй через 5 минут.")
        else:
            await msg.edit_text(f"❌ <b>Ошибка Telegram:</b> {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ <b>Критическая ошибка:</b> {e}")
        logging.exception("Критическая ошибка в get_new_name_and_copy")

    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()


@dp.message()
async def handle_other_messages(message: Message):
    await message.answer("Я не понимаю. Пожалуйста, отправь стикер или ссылку на стикерпак.")

# --- БЛОК ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def i_am_alive():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080)) 
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def main():
    logging.info("Бот запускается (через main)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Запуск Flask-потока...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    logging.info("Запуск основного asyncio-бота...")
    asyncio.run(main())