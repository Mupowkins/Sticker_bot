import asyncio
import logging
import os
import re
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, InputSticker

# --- Конфигурация ---
# 
# 🔴 ВНИМАНИЕ! 🔴
# Токен вписан прямо в код по вашему запросу.
# НЕ ЗАГРУЖАЙТЕ ЭТОТ ФАЙЛ В ПУБЛИЧНЫЙ GITHUB!
BOT_TOKEN = "8094703198:AAGBMM1a-MczaWtNZ0cjMmndImO_mPip_8I"
# 🔴 ----------------- 🔴
#
# Старая, безопасная строка:
# BOT_TOKEN = os.getenv("BOT_TOKEN") 
#

BOT_VERSION = "v1.1 (fix: link/sticker parsing)" 

NEW_PACK_TITLE = "ТГ Канал - @Mupowkins"
BOT_USERNAME_SUFFIX = "_by_Mupowkins_BOT" 
STICKER_LIMIT = 120

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация роутера
router = Router()


# --- Обработчики команд ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    Обработчик команды /start
    """
    await message.answer(
        "Привет! 👋\n\n"
        "Я бот для копирования стикерпаков.\n"
        "Просто отправь мне стикер из пака, который нужно скопировать, "
        "или ссылку на него (например, `t.me/addstickers/MyPack`).\n\n"
        f"<i>Версия: {BOT_VERSION}</i>"
    )


@router.message(F.sticker)
async def handle_sticker(message: types.Message):
    """
    Обработчик входящего стикера
    """
    if not message.sticker.set_name:
        await message.answer(
            "⚠️ <b>Ошибка:</b>\n"
            "Этот стикер не является частью какого-либо пака "
            "(возможно, это 'кастомный эмодзи' или одиночный стикер). "
            "Я не могу его скопировать."
        )
        return

    pack_name = message.sticker.set_name
    logger.info(f"Получен стикер из пака: {pack_name}")
    await process_sticker_pack(message, pack_name)


@router.message(F.text.regexp(r'.*t\.me/addstickers/([\w\d_]+)'))
async def handle_link(message: types.Message):
    """
    Обработчик ссылки на стикерпак
    """
    try:
        pack_name = re.search(r't\.me/addstickers/([\w\d_]+)', message.text).group(1)
    except Exception:
        await message.answer("⚠️ Не могу распознать ссылку. "
                             "Убедитесь, что она в формате `t.me/addstickers/PackName`")
        return

    logger.info(f"Получена ссылка на пак: {pack_name}")
    await process_sticker_pack(message, pack_name)


@router.message()
async def handle_other_messages(message: types.Message):
    """
    Обработчик любого другого текста, который не является ссылкой
    """
    await message.answer("Я не понимаю 😔\n"
                         "Пожалуйста, отправь мне <b>стикер</b> из пака "
                         "или <b>ссылку</b> на стикерпак.")


# --- Основная логика копирования ---

async def process_sticker_pack(message: types.Message, pack_name: str):
    """
    Главная функция, запускающая процесс копирования.
    """
    bot = message.bot
    try:
        await message.answer(f"✅ Получил пак: <code>{pack_name}</code>\n"
                             "Начинаю копирование. Это займет 1-2 минуты...")

        # 1. Получаем информацию об исходном паке
        sticker_set = await bot.get_sticker_set(pack_name)

        if not sticker_set.stickers:
            await message.answer("⚠️ <b>Ошибка:</b> В этом паке нет стикеров.")
            return
            
        # 2. Проверяем формат пака
        pack_format = sticker_set.sticker_format
        logger.info(f"Формат пака: {pack_format}. "
                    f"Количество стикеров: {len(sticker_set.stickers)}")
                    
        if pack_format == 'unknown':
            await message.answer("⚠️ <b>Ошибка:</b> Неизвестный формат стикерпака. "
                                 "Не могу скопировать.")
            return

        # 3. Генерируем имя для нового пака
        max_base_name_len = 64 - len(BOT_USERNAME_SUFFIX)
        new_pack_name = f"{sticker_set.name[:max_base_name_len]}{BOT_USERNAME_SUFFIX}"

        # 4. Скачиваем ПЕРВЫЙ стикер
        first_sticker = sticker_set.stickers[0]
        file_info = await bot.get_file(first_sticker.file_id)
        file_content = await bot.download_file(file_info.file_path)
        
        first_sticker_file = InputSticker(
            sticker=BufferedInputFile(file_content, filename=f"0.{pack_format}"),
            emoji_list=[first_sticker.emoji]
        )

        # 5. Создаем новый стикерпак
        try:
            await bot.create_new_sticker_set(
                user_id=message.from_user.id,
                name=new_pack_name,
                title=NEW_PACK_TITLE,
                stickers=[first_sticker_file],
                sticker_format=pack_format
            )
            logger.info(f"Создан новый пак: {new_pack_name}")
        except TelegramBadRequest as e:
            if "sticker set name is already occupied" in e.message:
                logger.warning(f"Имя {new_pack_name} уже занято.")
                await message.answer(
                    f"⚠️ <b>Ошибка:</b>\n"
                    f"Пак с именем <code>{new_pack_name}</code> уже существует. "
                    "Вероятно, вы уже копировали этот пак.\n"
                    f"Вот ссылка на него: t.me/addstickers/{new_pack_name}"
                )
                return
            elif "STICKERSET_NAME_INVALID" in e.message:
                logger.error(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Имя {new_pack_name} невалидно. "
                    f"Проверьте, что суффикс {BOT_USERNAME_SUFFIX} "
                    "совпадает с реальным @username бота!"
                )
                await message.answer(
                    "<b>КРИТИЧЕСКАЯ ОШИБКА API</b>\n"
                    "Имя пака не принято Telegram. "
                    "Вероятная причина: имя пользователя бота в коде "
                    f"(<code>{BOT_USERNAME_SUFFIX}</code>) "
                    "не совпадает с реальным именем вашего бота."
                )
                return
            else:
                logger.error(f"Неожиданная ошибка Telegram: {e}")
                await message.answer(f"<b>Ошибка Telegram API:</b>\n<code>{e.message}</code>")
                return

        await message.answer(f"✅ Пак успешно создан. "
                             f"Начинаю добавление остальных стикеров... "
                             f"(0/{len(sticker_set.stickers[1:STICKER_LIMIT])})")

        # 6. Добавляем ОСТАЛЬНЫЕ стикеры
        counter = 0
        total_to_copy = len(sticker_set.stickers[1:STICKER_LIMIT])

        for i, sticker in enumerate(sticker_set.stickers[1:STICKER_LIMIT]):
            try:
                # Скачиваем файл
                file_info = await bot.get_file(sticker.file_id)
                file_content = await bot.download_file(file_info.file_path)
                
                sticker_file = InputSticker(
                    sticker=BufferedInputFile(file_content, filename=f"{i+1}.{pack_format}"),
                    emoji_list=[sticker.emoji]
                )

                # Добавляем в пак
                await bot.add_sticker_to_set(
                    user_id=message.from_user.id,
                    name=new_pack_name,
                    sticker=sticker_file
                )
                
                counter += 1
                await asyncio.sleep(0.7) # Задержка для обхода Flood Control

                # Оповещаем пользователя о прогрессе каждые 20 стикеров
                if counter % 20 == 0 or counter == total_to_copy:
                    with suppress(TelegramBadRequest):
                        await message.edit_text(
                            f"✅ Пак успешно создан. "
                            f"Начинаю добавление остальных стикеров... "
                            f"({counter}/{total_to_copy})"
                        )

            except Exception as e:
                logger.error(f"Не удалось добавить стикер {i+1}: {e}")
                await message.answer(f"⚠️ Не удалось добавить стикер №{i+1}: <code>{e}</code>")
                await asyncio.sleep(1) 

        # 7. Отправляем финальную ссылку
        new_pack_link = f"https://t.me/addstickers/{new_pack_name}"
        await message.answer(
            f"🎉 <b>Готово!</b>\n\n"
            f"Все {counter + 1} стикеров скопированы.\n"
            f"Ваш новый пак: <b>{new_pack_link}</b>"
        )

    except TelegramBadRequest as e:
        logger.error(f"Ошибка API при обработке {pack_name}: {e}")
        await message.answer(f"<b>Ошибка Telegram API:</b>\n<code>{e.message}</code>\n\n"
                             "Возможно, пак защищен от копирования или удален.")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при обработке {pack_name}: {e}")
        await message.answer(f"<b>Неизвестная ошибка:</b>\n<code>{e}</code>")


# --- Запуск бота ---

async def main():
    """
    Главная функция запуска бота
    """
    if not BOT_TOKEN:
        logger.critical("Токен не найден! (Он должен быть вписан в код)")
        return

    bot = Bot(token=BOT_TOKEN, 
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    # Запускаем бота
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")