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
# ИСПРАВЛЕНИЕ: Добавляем DefaultBotProperties для ParseMode
from aiogram.client.bot import DefaultBotProperties

BOT_TOKEN = "8094703198:AAFzaULimXczgidjUtPlyRTw6z_p-i0xavk"

logging.basicConfig(level=logging.INFO)
# ИСПРАВЛЕНИЕ: Возвращаем ParseMode.HTML, чтобы бот понимал <b>, <i> и т.д.
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
    
    msg = await message.answer("⏳ <b>Начинаю копирование...</b>\nЭто займет некоторое время из-за задержек.")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        total_stickers = len(original_set.stickers)
        all_stickers = original_set.stickers

        sticker_format = "static"
        if original_set.is_animated:
            sticker_format = "animated"
        elif original_set.is_video:
            sticker_format = "video"

        # --- (!!!) НОВАЯ ЛОГИКА ЗАДЕРЖЕК (!!!) ---

        # ПАЧКА 1: (1-50 стикеров)
        first_batch_size = min(50, total_stickers)
        first_batch = all_stickers[:first_batch_size]
        first_batch_stickers = []
        
        for sticker in first_batch:
            emoji = sticker.emoji or "👍"
            first_batch_stickers.append(
                InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[emoji],
                    format=sticker_format # ИСПРАВЛЕНИЕ: это поле ОБЯЗАТЕЛЬНО
                )
            )

        if not first_batch_stickers:
            await msg.edit_text("❌ В этом паке нет стикеров.")
            await state.clear()
            return

        # Создаем пак
        await bot.create_new_sticker_set(
            user_id=user_id,
            name=new_name,
            title="ТГ Канал - @mupowkins",
            stickers=first_batch_stickers,
            sticker_format=sticker_format
        )

        # Проверяем, есть ли еще стикеры
        if total_stickers <= first_batch_size:
            await msg.edit_text(f"✅ <b>Готово!</b>\nПак скопирован: t.me/addstickers/{new_name}\nВсего стикеров: {total_stickers}")
            await state.clear()
            return

        # ЗАДЕРЖКА 1: 20 секунд (по твоему ТЗ)
        await msg.edit_text(f"✅ Добавлено {first_batch_size}/{total_stickers} стикеров.\n<b>Ожидаю 20 секунд...</b>")
        await asyncio.sleep(20.0)

        # ПАЧКИ 2-8: (51-120 стикеров)
        batches = [
            (51, 60), (61, 70), (71, 80), (81, 90), 
            (91, 100), (101, 110), (111, 120)
        ]

        for start, end in batches:
            # Проверяем, нужны ли еще итерации
            # (start-1) т.к. индексы с 0. (51-й стикер = индекс 50)
            if (start - 1) >= total_stickers:
                break 
                
            # Берем срез (e.g., [50:60] для 51-60)
            batch = all_stickers[start-1:end]
            
            if not batch:
                break # На всякий случай

            # Добавляем пачку из 10 стикеров (без задержек *внутри* пачки)
            for sticker in batch:
                emoji = sticker.emoji or "👍"
                sticker_obj = InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[emoji],
                    format=sticker_format # ИСПРАВЛЕНИЕ: это поле ОБЯЗАТЕЛЬНО
                )
                
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    sticker=sticker_obj
                )
            
            # Считаем, сколько всего добавлено
            current_total_added = min(end, total_stickers)
            
            # Проверяем, не закончили ли мы
            if current_total_added >= total_stickers:
                break # Закончили, выходим из цикла

            # ЗАДЕРЖКА 2: 15-20 секунд (по твоему ТЗ)
            delay = random.uniform(15.0, 20.0)
            await msg.edit_text(f"✅ Добавлено {current_total_added}/{total_stickers} стикеров.\n<b>Ожидаю {delay:.1f} секунд...</b>")
            await asyncio.sleep(delay)

        # --- Конец цикла ---

        await msg.edit_text(f"✅ <b>Готово!</b>\nПак скопирован: t.me/addstickers/{new_name}\nВсего стикеров: {total_stickers}")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text(f"❌ <b>Ошибка:</b> Имя <code>{new_name}</code> уже занято. Попробуй другое.")
            return # Не сбрасываем состояние, даем попробовать еще раз
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ <b>Ошибка:</b> Пак не найден. Возможно, ссылка битая.")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ <b>Слишком много запросов!</b>\nТелеграм временно ограничил бота. Пожалуйста, попробуй через 5 минут.")
        else:
            await msg.edit_text(f"❌ <b>Ошибка Telegram:</b> {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ <b>Критическая ошибка:</b> {e}")
        logging.exception("Критическая ошибка в get_new_name_and_copy")

    # Сбрасываем состояние в любом случае (кроме 'name taken')
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
    """Render будет стучаться сюда, чтобы проверить, 'жив' ли сервис"""
    return "Bot is alive!"

def run_flask():
    """Запускает веб-сервер в отдельном потоке"""
    port = int(os.environ.get("PORT", 8080)) 
    # Убираем debug и reloader, они не нужны в "production" на Render
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def main():
    """
    Главная функция для запуска бота.
    """
    logging.info("Бот запускается (через main)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Запуск Flask-потока...")
    # daemon=True гарантирует, что Flask-поток умрет, если основной (бот) упадет
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    logging.info("Запуск основного asyncio-бота...")
    asyncio.run(main())