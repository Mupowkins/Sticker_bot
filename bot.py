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
    await message.answer("Отправь стикер или ссылку на стикерпак\n*(v13 - Логика 'Сначала Видео')*")

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
    
    # Логика имени из твоего скриншота
    user_input_lower = user_input_name.lower()
    final_pack_name = f"{user_input_lower}_by_{me.username}"
    await message.answer(f"Я привел имя к стандарту. Финальное имя: <b>{final_pack_name}</b>")
    
    msg = await message.answer(f"⏳ Принято. Начинаю копирование для <b>{final_pack_name}</b>...")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        all_stickers = original_set.stickers
        total_stickers = len(all_stickers)
        
        # (!!!) ТВОЯ ЛОГИКА: ШАГ 1 - Найти первый видео-стикер (!!!)
        await msg.edit_text("Ищу первый видео-стикер, чтобы создать пак...")
        
        first_video_sticker = None
        first_video_sticker_obj = None
        first_video_index = -1

        for i, sticker in enumerate(all_stickers):
            if sticker.is_video:
                first_video_sticker = sticker
                first_video_index = i
                first_video_sticker_obj = InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[sticker.emoji or "🤩"],
                    format="video"
                )
                break
        
        if not first_video_sticker_obj:
            await msg.edit_text("❌ <b>Ошибка:</b> В этом паке не найдено <b>ни одного видео-стикера</b>. Не могу создать пак по твоей логике. Отмена.")
            await state.clear()
            return
        
        # (!!!) ТВОЯ ЛОГИКА: ШАГ 2 - Создать пак (!!!)
        await msg.edit_text(f"Создаю <b>video</b>-пак с первым видео-стикером...")
        
        await bot.create_new_sticker_set(
            user_id=user_id,
            name=final_pack_name,
            title="ТГ Канал - @mupowkins",
            stickers=[first_video_sticker_obj], # Отправляем только один видео-стикер
            sticker_format="video"
        )
        
        await msg.edit_text(f"✅ Пак создан. Ожидаю 12 секунд...")
        await asyncio.sleep(12) 

        # (!!!) ТВОЯ ЛОГИКА: ШАГ 3 - Добавить ВСЕ ОСТАЛЬНЫЕ (!!!)
        
        # Собираем список всех остальных стикеров
        remaining_stickers = []
        for i, sticker in enumerate(all_stickers):
            if i != first_video_index: # Пропускаем тот, что уже добавили
                remaining_stickers.append(sticker)
        
        total_remaining = len(remaining_stickers)
        if total_remaining == 0:
            await msg.edit_text(f"✅ Готово! (был только 1 стикер)\nt.me/addstickers/{final_pack_name}")
            await state.clear()
            return

        await msg.edit_text(f"Добавляю оставшиеся {total_remaining} стикеров пачками по 25...")
        
        batch_size = 25
        copied_count = 1 # Уже скопировали 1

        for i in range(0, total_remaining, batch_size):
            batch = remaining_stickers[i:i + batch_size]
            
            await msg.edit_text(f"⏳ Добавляю стикеры {copied_count + 1} - {copied_count + len(batch)}...")
            
            for sticker in batch:
                # Определяем "родной" формат стикера
                if sticker.is_video:
                    sticker_format = "video"
                elif sticker.is_animated:
                    sticker_format = "animated"
                else:
                    sticker_format = "static"
                    
                sticker_to_add = InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[sticker.emoji or "🤩"],
                    format=sticker_format # Пытаемся добавить стикер с его "родным" форматом
                )
                
                # (!!!) ВОТ ЗДЕСЬ КОД УПАДЕТ (!!!)
                # когда sticker_format будет "static" или "animated"
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=final_pack_name,
                    sticker=sticker_to_add
                )
                # Если код не упал, значит стикер был 'video'
                copied_count += 1
            
            # Если пачка добавилась, ждем
            await msg.edit_text(f"✅ Добавлено {copied_count}/{total_stickers}. Ожидаю 12 секунд...")
            await asyncio.sleep(12)

        await msg.edit_text(f"✅ <b>УСПЕХ (???)</b>\nПак создан: t.me/addstickers/{final_pack_name}\nСкопировано: {copied_count}/{total_stickers}")

    except TelegramBadRequest as e:
        # (!!!) СЮДА ОН СКОРЕЕ ВСЕГО ПОПАДЕТ (!!!)
        if "sticker set name is already taken" in str(e):
            await msg.edit_text(f"❌ Имя <b>{final_pack_name}</b> уже занято. Попробуй другое.")
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Пак не найден")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ Слишком быстро! Подожди 30 секунд.")
        # ---
        elif "STICKER_PNG_NOPNG" in str(e) or "STICKER_TGS_NOTGS" in str(e) or "STICKER_FORMAT_INVALID" in str(e):
            await msg.edit_text(f"❌ <b>ВОТ ОНА, ОШИБКА: {e}</b>\n\nTelegram <b>ЗАПРЕТИЛ</b> добавлять стикер другого формата в <b>video</b>-пак. Копирование остановлено.")
        # ---
        else:
            await msg.edit_text(f"❌ Неизвестная Ошибка Telegram: {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ Критическая ошибка: {e}")

    await state.clear()


@dp.message()
async def handle_other_messages(message: Message):
    await message.answer("Отправь стикер или ссылку")

# --- БЛОК ДЛЯ RENDER ---
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