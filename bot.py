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

BOT_TOKEN = "8094703198:AAFzaULimXczgidjUtPlyRTw6z_p-i0xavk"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class CopyPack(StatesGroup):
    waiting_for_new_name = State()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Отправь стикер или ссылку на стикерпак\n*(v10 - поддержка смешанных стикеров)*")

@dp.message(F.sticker)
async def handle_sticker(message: Message, state: FSMContext):
    if not message.sticker.set_name:
        await message.answer("Этот стикер не из пака")
        return
    
    await state.update_data(original_set_name=message.sticker.set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    me = await bot.get_me()
    await message.answer(f"Придумай имя для нового пака (я добавлю <i>_by_{me.username}_</i>)")

@dp.message(F.text.regexp(r"t\.me/addstickers/([a-zA-Z0-9_]+)"))
async def handle_link(message: Message, state: FSMContext):
    original_set_name = re.search(r"t\.me/addstickers/([a-zA-Z0-9_]+)", message.text).group(1)
    
    await state.update_data(original_set_name=original_set_name)
    await state.set_state(CopyPack.waiting_for_new_name)
    
    me = await bot.get_me()
    await message.answer(f"Придумай имя для нового пака (я добавлю <i>_by_{me.username}_</i>)")

@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    user_data = await state.get_data()
    
    if not user_data:
        await message.answer("Ой! Кажется, я 'заснул' и забыл, какой пак мы копируем. Начнем заново. Пожалуйста, отправь мне стикер еще раз.")
        await state.clear()
        return

    original_set_name = user_data.get("original_set_name")
    user_input_name = message.text.strip()
    user_id = message.from_user.id

    me = await bot.get_me()
    bot_suffix = f"_by_{me.username}" 
    
    clean_bot_suffix = f"by_{me.username}"
    user_input_lower = user_input_name.lower()
    suffix_lower = clean_bot_suffix.lower() 

    if user_input_lower.endswith(suffix_lower):
        index = user_input_lower.rfind(suffix_lower)
        base_name = user_input_name[:index]
    elif user_input_lower.endswith(f"_{suffix_lower}"):
        index = user_input_lower.rfind(f"_{suffix_lower}")
        base_name = user_input_name[:index]
    else:
        base_name = user_input_name

    base_name = base_name.rstrip('_')
    new_name = base_name + bot_suffix
    
    if new_name != user_input_name:
         await message.answer(f"Я привел имя к стандарту. Финальное имя: <b>{new_name}</b>")
    
    msg = await message.answer(f"⏳ Принято. Начинаю копирование для <b>{new_name}</b>...")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        total_stickers = len(original_set.stickers)
        all_stickers = original_set.stickers
        
        # Классифицируем стикеры по форматам
        video_stickers = []
        animated_stickers = []
        static_stickers = []
        
        for sticker in all_stickers:
            if sticker.is_video:
                video_stickers.append(sticker)
            elif sticker.is_animated:
                animated_stickers.append(sticker)
            else:
                static_stickers.append(sticker)
        
        # Определяем основной формат для создания пака (по большинству стикеров)
        format_counts = {
            "video": len(video_stickers),
            "animated": len(animated_stickers),
            "static": len(static_stickers)
        }
        main_format = max(format_counts, key=format_counts.get)
        
        await msg.edit_text(f"🔄 Найден смешанный пак ({total_stickers} стикеров): "
                          f"📹 {len(video_stickers)} видео, "
                          f"🎬 {len(animated_stickers)} анимированных, "
                          f"🖼 {len(static_stickers)} статичных\n"
                          f"Создаю пак формата <b>{main_format}</b>...")
        
        # Собираем все стикеры в правильном порядке, но конвертируем форматы
        processed_stickers = []
        
        for sticker in all_stickers:
            emoji = sticker.emoji or "👍"
            
            # Определяем формат текущего стикера
            if sticker.is_video:
                sticker_format = "video"
            elif sticker.is_animated:
                sticker_format = "animated"
            else:
                sticker_format = "static"
            
            # Если формат стикера не совпадает с основным форматом пака,
            # мы все равно добавляем его, но в основном формате пака
            # Telegram автоматически конвертирует форматы при добавлении
            processed_stickers.append(
                InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[emoji],
                    format=main_format  # Используем основной формат пака для всех стикеров
                )
            )

        if not processed_stickers:
            await msg.edit_text("❌ В этом паке нет стикеров.")
            await state.clear()
            return

        # Создаем пак с первыми 50 стикерами
        first_batch = processed_stickers[:50]
        
        try:
            await bot.create_new_sticker_set(
                user_id=user_id,
                name=new_name,
                title="ТГ Канал - @mupowkins",
                stickers=first_batch,
                sticker_format=main_format
            )
        except TelegramBadRequest as e:
            if "Flood control" in str(e) or "Too Many Requests" in str(e):
                match = re.search(r"retry after (\d+)", str(e))
                wait_time = int(match.group(1)) + 2 if match else 30
                await msg.edit_text(f"❗️ <b>Флуд-контроль на создании пака!</b>\nЖду {wait_time}с...")
                await asyncio.sleep(wait_time)
                await bot.create_new_sticker_set(
                    user_id=user_id,
                    name=new_name,
                    title="ТГ Канал - @mupowkins",
                    stickers=first_batch,
                    sticker_format=main_format
                )
            else:
                raise
        
        # Задержка 12 секунд
        await msg.edit_text(f"✅ Создан пак с первыми {len(first_batch)} стикерами.\nОжидание ~12 секунд...")
        await asyncio.sleep(12) 

        # Добавляем оставшиеся стикеры пачками по 25
        if total_stickers > 50:
            
            batches_config = [
                (50, 75),  # 51-75 (25 стикеров)
                (75, 100), # 76-100 (25 стикеров)
                (100, 120) # 101-120 (20 стикеров)
            ]

            for start_idx, end_idx in batches_config:
                
                if start_idx >= total_stickers:
                    break 
                    
                batch = processed_stickers[start_idx:end_idx]
                if not batch:
                    break
                
                await msg.edit_text(f"⏳ Добавляю стикеры {start_idx+1}-{min(end_idx, total_stickers)}...")
                
                for sticker_obj in batch:
                    try:
                        await bot.add_sticker_to_set(
                            user_id=user_id,
                            name=new_name,
                            sticker=sticker_obj
                        )
                    except TelegramBadRequest as e:
                         if "Flood control" in str(e) or "Too Many Requests" in str(e):
                            await msg.edit_text(f"❗️ <b>Флуд-контроль на добавлении!</b>\nСплю 15с...")
                            await asyncio.sleep(15.0)
                            await bot.add_sticker_to_set(
                                user_id=user_id,
                                name=new_name,
                                sticker=sticker_obj
                            )
                         else:
                            raise e
                
                current_progress = min(end_idx, total_stickers)
                
                if current_progress < total_stickers:
                    await msg.edit_text(f"✅ Добавлено {current_progress}/{total_stickers}\nОжидание ~12 секунд...")
                    await asyncio.sleep(12) 

        await msg.edit_text(f"✅ Готово!\n<b>{main_format}</b> пак создан!\nt.me/addstickers/{new_name}\n"
                          f"Стикеров скопировано: {total_stickers}\n"
                          f"(📹 {len(video_stickers)} видео, "
                          f"🎬 {len(animated_stickers)} анимированных, "
                          f"🖼 {len(static_stickers)} статичных)")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text("❌ Имя занято")
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Пак не найден")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ Слишком быстро! Подожди 30 секунд.")
        elif "STICKER_PNG_NOPNG" in str(e) or "STICKER_TGS_NOTGS" in str(e) or "STICKER_WEBM_NOWEBM" in str(e):
            await msg.edit_text("❌ Ошибка формата стикеров. Telegram не может обработать некоторые форматы.")
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