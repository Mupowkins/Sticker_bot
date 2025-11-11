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

# --- (!!!) ИЗМЕНЕНИЕ ЗДЕСЬ (!!!) ---
# Нам нужно импортировать DefaultBotProperties
from aiogram.client.bot import DefaultBotProperties 

# --- Конфигурация ---
BOT_TOKEN = os.environ.get("BOT_TOKEN") 

if not BOT_TOKEN:
    logging.critical("Критическая ошибка: Токен BOT_TOKEN не найден в переменных окружения.")
    exit()

logging.basicConfig(level=logging.INFO)

# --- (!!!) ИЗМЕНЕНИЕ ЗДЕСЬ (!!!) ---
# Старый код:
# bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
#
# Новый код для aiogram 3.7+
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()


# --- Машина состояний (FSM) ---
class CopyPack(StatesGroup):
    waiting_for_new_title = State()
    waiting_for_new_name = State()


# --- Обработчики (Хэндлеры) ---
# (Тут все твои хэндлеры, они не изменились)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! 👋 Я бот для копирования стикерпаков.\n\n"
        "Отправь мне **любой стикер** из пака, который хочешь скопировать, "
        "или **ссылку** на пак (вида `t.me/addstickers/название`).\n\n"
        "Я создам для тебя полную копию этого пака, владельцем которой будешь ты."
    )

@dp.message(F.sticker)
async def handle_sticker(message: Message, state: FSMContext):
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
        f"Пример: `my_cool_pack_by_{bot_username}`"
    )


@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    user_data = await state.get_data()
    original_set_name = user_data.get("original_set_name")
    new_title = user_data.get("new_title")
    new_name = message.text
    user_id = message.from_user.id

    me = await bot.get_me()
    bot_suffix = f"_by_{me.username}"
    if not new_name.endswith(bot_suffix):
        await message.answer(
            f"❌ Ошибка. Имя пака **должно** заканчиваться на `{bot_suffix}`.\n\n"
            f"Попробуй еще раз. Например: `{new_name}{bot_suffix}`"
        )
        return

    msg = await message.answer("Принято. Начинаю процесс копирования... Это может занять несколько минут для больших паков.")

    try:
        original_set = await bot.get_sticker_set(original_set_name)

        sticker_format = "static"
        if original_set.is_animated:
            sticker_format = "animated"
        elif original_set.is_video:
            sticker_format = "video"
        
        stickers_to_add = []
        for sticker in original_set.stickers:
            stickers_to_add.append(
                InputSticker(
                    sticker=sticker.file_id, 
                    emoji_list=[sticker.emoji]
                )
            )

        if not stickers_to_add:
            await msg.edit_text("Не могу поверить, но в этом паке нет стикеров. Копирование отменено.")
            await state.clear()
            return

        await bot.create_new_sticker_set(
            user_id=user_id,
            name=new_name,
            title=new_title,
            stickers=[stickers_to_add[0]],
            sticker_format=sticker_format
        )
        
        if len(stickers_to_add) > 1:
            for i, sticker in enumerate(stickers_to_add[1:], start=1):
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    sticker=sticker
                )
                if i % 10 == 0 or i == len(stickers_to_add) - 1:
                    await msg.edit_text(f"Копирую... {i+1}/{len(stickers_to_add)}")
                
                await asyncio.