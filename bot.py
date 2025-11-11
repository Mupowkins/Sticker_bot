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

        # Определяем тип стикеров для старого API
        if original_set.is_video:
            sticker_type = "video"
        elif original_set.is_animated:
            sticker_type = "animated"
        else:
            sticker_type = "regular"

        all_stickers = original_set.stickers
        
        # ПАЧКА 1: создаем пак с 1 стикером (старый метод)
        await msg.edit_text("🔄 Создаю пак...")
        first_sticker = all_stickers[0]
        emoji = first_sticker.emoji or "👍"

        # Используем старый метод создания
        if sticker_type == "video":
            await bot.create_new_sticker_set(
                user_id=user_id,
                name=new_name,
                title="ТГ Канал - @mupowkins",
                webm_sticker=first_sticker.file_id,
                emojis=emoji
            )
        elif sticker_type == "animated":
            await bot.create_new_sticker_set(
                user_id=user_id,
                name=new_name,
                title="ТГ Канал - @mupowkins", 
                tgs_sticker=first_sticker.file_id,
                emojis=emoji
            )
        else:
            await bot.create_new_sticker_set(
                user_id=user_id,
                name=new_name,
                title="ТГ Канал - @mupowkins",
                png_sticker=first_sticker.file_id,
                emojis=emoji
            )

        await msg.edit_text("✅ Пак создан\nДобавляю стикеры... 1/120")
        
        # Добавляем остальные стикеры по одному с задержкой 1 секунда
        for i, sticker in enumerate(all_stickers[1:], 2):
            emoji = sticker.emoji or "👍"
            
            # Используем старый метод добавления
            if sticker_type == "video":
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    webm_sticker=sticker.file_id,
                    emojis=emoji
                )
            elif sticker_type == "animated":
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    tgs_sticker=sticker.file_id,
                    emojis=emoji
                )
            else:
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    png_sticker=sticker.file_id,
                    emojis=emoji
                )
            
            # Маленькая задержка 1 секунда
            await asyncio.sleep(1)
            
            if i % 10 == 0:
                await msg.edit_text(f"✅ Добавлено {i}/120")

        await msg.edit_text(f"✅ Готово!\nt.me/addstickers/{new_name}\nСтикеров: {total_stickers}")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text("❌ Имя занято")
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Пак не найден")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ Слишком быстро! Попробуй через 30 секунд.")
        else:
            await msg.edit_text(f"❌ Ошибка: {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")

    await state.clear()