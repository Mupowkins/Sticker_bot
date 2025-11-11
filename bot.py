import os
import threading
import http.server
import socketserver
import logging
import re
import asyncio
from io import BytesIO
from typing import Dict

from telegram import Update, InputFile, InputSticker, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from telegram.constants import StickerFormat

# ---------- Вспомогательная "заглушка" для Render ----------
def keep_alive():
    """Запуск простого HTTP сервера, чтобы Render не останавливал процесс."""
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"⚡ Keep-alive сервер запущен на порту {port}")
        httpd.serve_forever()

# Запускаем в отдельном потоке
threading.Thread(target=keep_alive, daemon=True).start()

# ---------- Настройка логов ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Глобальные состояния пользователей ----------
USER_STATE: Dict[int, dict] = {}

# Состояния для ConversationHandler
GET_STICKER_OR_LINK, GET_NEW_NAME, GET_NEW_SHORT_NAME = range(3)

# Токен бота из нашего диалога
TOKEN = "8094703198:AAEszw3K_62yU3oHR0cW3RHvXfxBeUJhy6A"

# ---------- Хелперы ----------
def ensure_bot_suffix(name: str, bot_username: str) -> str:
    """Гарантировать, что имя набора заканчивается на _by_<bot_username>"""
    if not name.endswith(f"_by_{bot_username}"):
        base = re.sub(r'[^a-z0-9_]', '_', name.lower())
        return f"{base}_by_{bot_username}"
    return name

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - начало работы с ботом"""
    # Устанавливаем команды меню
    commands = [
        BotCommand("start", "🔄 Начать работу"),
        BotCommand("help", "ℹ️ Помощь"),
        BotCommand("about", "📚 О проекте")
    ]
    await context.bot.set_my_commands(commands)
    
    await update.message.reply_text(
        "👋 <b>Добро пожаловать в StickerPack Copier Bot!</b>\n\n"
        "🎓 <i>Курсовая работа по информатике</i>\n\n"
        "🚀 <b>Я умею копировать стикерпаки:</b>\n"
        "• 📝 Обычные стикеры\n"
        "✨ Анимированные стикеры\n"
        "🎥 Видео стикеры\n\n"
        "💡 <b>Как использовать:</b>\n"
        "1. Отправь мне любой стикер ИЛИ ссылку на стикерпак\n"
        "2. Придумай новое название\n"
        "3. Выбери уникальную ссылку\n"
        "4. Получи готовый стикерпак!\n\n"
        "🔹 <b>Просто отправь стикер или ссылку чтобы начать!</b>",
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help - справка по использованию"""
    await update.message.reply_text(
        "📖 <b>Руководство по использованию бота</b>\n\n"
        "🔹 <b>Способ 1: Через стикер</b>\n"
        "• Отправь любой стикер из нужного пака\n"
        "• Бот автоматически найдет весь стикерпак\n"
        "• Заполни форму и получи копию\n\n"
        "🔹 <b>Способ 2: Через ссылку</b>\n"
        "• Отправь ссылку на стикерпак:\n"
        "  <code>https://t.me/addstickers/имя_пака</code>\n\n"
        "🔹 <b>Поддерживаемые типы стикеров:</b>\n"
        "🖼️ Обычные стикеры\n"
        "✨ Анимированные стикеры\n"
        "🎥 Видео стикеры\n\n"
        "🎯 <b>Начни с отправки стикера или ссылки!</b>",
        parse_mode="HTML"
    )

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /about - информация о проекте"""
    await update.message.reply_text(
        "🎓 <b>StickerPack Copier Bot</b>\n\n"
        "📚 <i>Курсовая работа по информатике</i>\n\n"
        "🔧 <b>Технические особенности:</b>\n"
        "• Python 3.11\n"
        "• python-telegram-bot 20.7\n"
        "• Асинхронное программирование\n"
        "• Telegram Bot API\n\n"
        "⚙️ <b>Функциональность:</b>\n"
        "• Копирование любых стикерпаков\n"
        "• Поддержка всех типов стикеров\n"
        "• Смена названий и ссылок\n"
        "• Простой и интуитивный интерфейс\n\n"
        "👨‍💻 <b>Разработчик:</b> Студент техникума\n"
        "📅 <b>Год:</b> 2024",
        parse_mode="HTML"
    )

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка отправленного стикера"""
    try:
        sticker = update.message.sticker
        await update.message.reply_text("🔍 Нашел стикер! Ищу весь стикерпак...")
        
        # Получаем информацию о стикерпаке
        sticker_set = await context.bot.get_sticker_set(sticker.set_name)
        
        # Сохраняем данные стикерпака
        context.user_data['original_sticker_set'] = sticker_set
        context.user_data['sticker_count'] = len(sticker_set.stickers)
        
        # Определяем тип стикеров
        first_sticker = sticker_set.stickers[0]
        sticker_type = "🖼️ Обычные стикеры"
        if hasattr(first_sticker, 'is_video') and first_sticker.is_video:
            sticker_type = "🎥 Видео стикеры"
        elif hasattr(first_sticker, 'is_animated') and first_sticker.is_animated:
            sticker_type = "✨ Анимированные стикеры"
        
        # Показываем информацию о найденном стикерпаке
        info_text = (
            f"✅ <b>Стикерпак найден!</b>\n\n"
            f"📛 <b>Текущее название:</b> {sticker_set.title}\n"
            f"📊 <b>Количество стикеров:</b> {len(sticker_set.stickers)}\n"
            f"🎨 <b>Тип стикеров:</b> {sticker_type}\n"
            f"🔗 <b>Текущая ссылка:</b> t.me/addstickers/{sticker.set_name}\n\n"
            f"✏️ <b>Введи новое название для стикерпака:</b>"
        )
        
        await update.message.reply_html(info_text)
        return GET_NEW_NAME
        
    except Exception as e:
        logger.error(f"Ошибка обработки стикера: {e}")
        await update.message.reply_text(
            "❌ Не удалось найти стикерпак.\n"
            "Убедись, что стикер из существующего набора.\n\n"
            "Попробуй отправить другой стикер или ссылку на стикерпак."
        )
        return GET_STICKER_OR_LINK

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка текстового сообщения (ссылки)"""
    try:
        user_input = update.message.text.strip()
        
        # Проверяем, является ли сообщение ссылкой на стикерпак
        if "t.me/addstickers/" in user_input:
            # Извлекаем короткое имя из ссылки
            short_name = user_input.split("t.me/addstickers/")[-1].split('?')[0].split('/')[0].strip()
            
            if not short_name:
                await update.message.reply_text("❌ Неверный формат ссылки. Попробуй еще раз:")
                return GET_STICKER_OR_LINK
            
            await update.message.reply_text("🔍 Ищу стикерпак по ссылке...")
            
            # Получаем информацию о стикерпаке
            sticker_set = await context.bot.get_sticker_set(short_name)
            
            # Сохраняем данные
            context.user_data['original_sticker_set'] = sticker_set
            context.user_data['sticker_count'] = len(sticker_set.stickers)
            context.user_data['original_short_name'] = short_name
            
            # Определяем тип стикеров
            first_sticker = sticker_set.stickers[0]
            sticker_type = "🖼️ Обычные стикеры"
            if hasattr(first_sticker, 'is_video') and first_sticker.is_video:
                sticker_type = "🎥 Видео стикеры"
            elif hasattr(first_sticker, 'is_animated') and first_sticker.is_animated:
                sticker_type = "✨ Анимированные стикеры"
            
            # Показываем информацию
            info_text = (
                f"✅ <b>Стикерпак найден по ссылке!</b>\n\n"
                f"📛 <b>Текущее название:</b> {sticker_set.title}\n"
                f"📊 <b>Количество стикеров:</b> {len(sticker_set.stickers)}\n"
                f"🎨 <b>Тип стикеров:</b> {sticker_type}\n"
                f"🔗 <b>Текущая ссылка:</b> t.me/addstickers/{short_name}\n\n"
                f"✏️ <b>Введи новое название для стикерпака:</b>"
            )
            
            await update.message.reply_html(info_text)
            return GET_NEW_NAME
            
        else:
            # Если это не ссылка, просим отправить стикер или ссылку
            await update.message.reply_text(
                "📝 Отправь мне:\n"
                "• 🎨 Любой стикер из нужного пака\n"
                "• 🔗 Или ссылку на стикерпак\n\n"
                "Формат ссылки: https://t.me/addstickers/имя_пака"
            )
            return GET_STICKER_OR_LINK
            
    except Exception as e:
        logger.error(f"Ошибка обработки текста: {e}")
        await update.message.reply_text(
            f"❌ Не удалось найти стикерпак: {str(e)}\n\n"
            "Проверь правильность ссылки и попробуй еще раз."
        )
        return GET_STICKER_OR_LINK

async def get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение нового названия стикерпака"""
    try:
        new_title = update.message.text.strip()
        
        if not new_title:
            await update.message.reply_text("❌ Название не может быть пустым. Введи название:")
            return GET_NEW_NAME
        
        if len(new_title) > 64:
            await update.message.reply_text("❌ Слишком длинное название (макс. 64 символа). Введи короче:")
            return GET_NEW_NAME
        
        # Сохраняем новое название
        context.user_data['new_title'] = new_title
        
        instruction_text = (
            "✅ <b>Название принято!</b>\n\n"
            "🔗 <b>Теперь придумай короткое имя для ссылки:</b>\n\n"
            "📋 <b>Требования:</b>\n"
            "• Только латинские буквы (a-z, A-Z)\n"
            "• Цифры (0-9)\n"
            "• Нижнее подчеркивание (_)\n"
            "• Длина: 5-32 символа\n\n"
            "💡 <b>Примеры:</b>\n"
            "• <code>MyCoolStickers2024</code>\n"
            "• <code>best_stickers_pack</code>\n"
            "• <code>project_work_stickers</code>\n\n"
            "✏️ Введи короткое имя:"
        )
        
        await update.message.reply_html(instruction_text)
        return GET_NEW_SHORT_NAME
        
    except Exception as e:
        logger.error(f"Ошибка в get_new_name: {e}")
        await update.message.reply_text("❌ Ошибка. Попробуй еще раз:")
        return GET_NEW_NAME

async def get_new_short_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение короткого имени и создание копии стикерпака"""
    try:
        new_short_name = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Валидация короткого имени
        if not new_short_name or len(new_short_name) < 5 or len(new_short_name) > 32:
            await update.message.reply_text("❌ Длина должна быть 5-32 символа. Введи еще раз:")
            return GET_NEW_SHORT_NAME
        
        if not all(c.isalnum() or c == '_' for c in new_short_name):
            await update.message.reply_text(
                "❌ Можно использовать только латинские буквы, цифры и подчеркивание. Введи еще раз:"
            )
            return GET_NEW_SHORT_NAME
        
        # Получаем сохраненные данные
        original_sticker_set = context.user_data.get('original_sticker_set')
        new_title = context.user_data.get('new_title')
        
        if not original_sticker_set or not new_title:
            await update.message.reply_text("❌ Данные утеряны. Начни заново, отправив стикер или ссылку.")
            return ConversationHandler.END
        
        # Начинаем процесс создания копии
        progress_msg = await update.message.reply_text(
            "🔄 Начинаю создание копии стикерпака...\n"
            "Это может занять несколько минут в зависимости от количества стикеров."
        )
        
        # Определяем формат стикеров на основе первого стикера
        first_sticker = original_sticker_set.stickers[0]
        
        if hasattr(first_sticker, 'is_video') and first_sticker.is_video:
            sticker_format = StickerFormat.VIDEO
        elif hasattr(first_sticker, 'is_animated') and first_sticker.is_animated:
            sticker_format = StickerFormat.ANIMATED
        else:
            sticker_format = StickerFormat.STATIC
        
        # Создаем первый стикер для нового набора
        input_sticker = InputSticker(
            sticker=first_sticker.file_id,
            emoji_list=first_sticker.emoji if hasattr(first_sticker, 'emoji') and first_sticker.emoji else ['🙂']
        )
        
        # Создаем новый стикерпак
        await context.bot.create_new_sticker_set(
            user_id=user_id,
            name=new_short_name,
            title=new_title,
            stickers=[input_sticker],
            sticker_format=sticker_format
        )
        
        # Добавляем остальные стикеры
        success_count = 1
        total_stickers = len(original_sticker_set.stickers)
        
        for i, sticker in enumerate(original_sticker_set.stickers[1:], 2):
            try:
                input_sticker = InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=sticker.emoji if hasattr(sticker, 'emoji') and sticker.emoji else ['🙂']
                )
                
                await context.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_short_name,
                    sticker=input_sticker
                )
                success_count += 1
                
                # Отправляем прогресс каждые 10 стикеров
                if i % 10 == 0:
                    await update.message.reply_text(f"📦 Обработано {i}/{total_stickers} стикеров...")
                
                # Задержка для избежания ограничений API
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Не удалось добавить стикер {i}: {e}")
                continue
        
        # Формируем ссылку на новый стикерпак
        sticker_link = f"https://t.me/addstickers/{new_short_name}"
        
        # Финальное сообщение об успехе
        success_text = (
            f"🎉 <b>Стикерпак успешно создан!</b>\n\n"
            f"📛 <b>Название:</b> {new_title}\n"
            f"🔗 <b>Ссылка для добавления:</b>\n<code>{sticker_link}</code>\n"
            f"📊 <b>Скопировано стикеров:</b> {success_count}/{total_stickers}\n\n"
            f"✨ <b>Чтобы добавить стикерпак:</b>\n"
            f"1. Нажми на ссылку выше\n"
            f"2. Или вручную: t.me/addstickers/{new_short_name}\n\n"
            f"🚀 <b>Создать еще один?</b> Просто отправь новый стикер или ссылку!"
        )
        
        await progress_msg.delete()
        await update.message.reply_html(success_text)
        
        # Логируем успешное создание
        logger.info(f"Создан новый стикерпак: {new_short_name} ({success_count}/{total_stickers} стикеров)")
        
    except Exception as e:
        logger.error(f"Ошибка создания стикерпака: {e}")
        error_msg = str(e)
        
        if "sticker set name is already occupied" in error_msg:
            await update.message.reply_text(
                "❌ Это короткое имя уже занято. Придумай другое уникальное имя:"
            )
            return GET_NEW_SHORT_NAME
        else:
            await update.message.reply_text(
                f"❌ <b>Ошибка при создании стикерпака:</b>\n"
                f"<code>{error_msg}</code>\n\n"
                f"Попробуй начать заново, отправив стикер или ссылку.",
                parse_mode='HTML'
            )
    
    finally:
        # Очищаем данные пользователя
        context.user_data.clear()
        return ConversationHandler.END

async def handle_other_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка других сообщений"""
    await update.message.reply_text(
        "👋 <b>StickerPack Copier Bot</b>\n\n"
        "🎓 <i>Курсовой проект по информатике</i>\n\n"
        "💡 <b>Чтобы начать работу:</b>\n"
        "• Отправь любой стикер\n"
        "• Или ссылку на стикерпак\n\n"
        "📖 Подробнее: /help",
        parse_mode='HTML'
    )

# ---------- Основная функция ----------
def main():
    # Используем токен из нашего диалога
    app = ApplicationBuilder().token(TOKEN).build()

    # ConversationHandler для основного процесса
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Sticker.ALL, handle_sticker),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
        ],
        states={
            GET_STICKER_OR_LINK: [
                MessageHandler(filters.Sticker.ALL, handle_sticker),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
            ],
            GET_NEW_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_name)
            ],
            GET_NEW_SHORT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_short_name)
            ],
        },
        fallbacks=[
            CommandHandler("start", start)
        ],
        allow_reentry=True
    )
    
    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    
    # Регистрируем ConversationHandler
    app.add_handler(conv_handler)
    
    # Обработчик для всех остальных сообщений
    app.add_handler(MessageHandler(filters.ALL, handle_other_messages))

    logger.info("🤖 Бот запущен (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()