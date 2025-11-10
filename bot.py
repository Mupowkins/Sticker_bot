import logging
import os
import asyncio
from telegram import (
    Update, 
    InputSticker, 
    BotCommand
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    ConversationHandler
)
from telegram.constants import StickerFormat

# ==================== НАСТРОЙКИ ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Состояния для ConversationHandler
GET_STICKER_SET_LINK, GET_NEW_NAME, GET_NEW_SHORT_NAME = range(3)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== ФУНКЦИИ БОТА ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        
        commands = [
            BotCommand("start", "🔄 Начать работу"),
            BotCommand("copy", "📦 Скопировать стикерпак"),
            BotCommand("help", "ℹ️ Помощь")
        ]
        await context.bot.set_my_commands(commands)
        
        welcome_text = (
            "👋 <b>Привет, {user_name}!</b>\n\n"
            "Я помогу тебе создавать копии стикерпаков с новыми названиями.\n\n"
            "🚀 <b>Как использовать:</b>\n"
            "1. Отправь /copy\n"
            "2. Пришли ссылку на стикерпак\n"
            "3. Укажи новое название\n"
            "4. Придумай короткое имя для ссылки\n\n"
            "📝 <b>Пример ссылки:</b>\n"
            "<code>https://t.me/addstickers/Animals</code>\n\n"
            "🔹 <b>Начнем:</b> Отправь /copy"
        ).format(user_name=user.first_name)
        
        await update.message.reply_html(welcome_text)
        
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await update.message.reply_text("❌ Произошла ошибка.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = (
        "📖 <b>Инструкция:</b>\n\n"
        "1. <b>Отправь</b> /copy\n"
        "2. <b>Пришли ссылку</b> на стикерпак:\n"
        "   <code>https://t.me/addstickers/Name</code>\n"
        "3. <b>Укажи новое название</b>\n"
        "4. <b>Придумай короткое имя</b> (латинские буквы)\n\n"
        "💡 <b>Пример короткого имени:</b>\n"
        "   • MyStickers2024\n"
        "   • best_pack\n"
        "   • cool_stickers\n\n"
        "🚀 <b>Начать:</b> /copy"
    )
    await update.message.reply_html(help_text)

async def start_copy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало копирования"""
    try:
        context.user_data.clear()
        
        await update.message.reply_html(
            "📦 <b>Копирование стикерпака</b>\n\n"
            "🔗 <b>Шаг 1:</b> Пришли ссылку на стикерпак:\n\n"
            "📝 <b>Пример:</b>\n"
            "<code>https://t.me/addstickers/Animals</code>\n\n"
            "❌ <b>Отмена:</b> /start"
        )
        return GET_STICKER_SET_LINK
        
    except Exception as e:
        logger.error(f"Ошибка в start_copy: {e}")
        await update.message.reply_text("❌ Ошибка.")
        return ConversationHandler.END

async def get_sticker_set_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение ссылки на стикерпак"""
    try:
        user_input = update.message.text.strip()
        logger.info(f"Ссылка: {user_input}")
        
        # Извлекаем короткое имя
        if "t.me/addstickers/" in user_input:
            short_name = user_input.split("t.me/addstickers/")[-1].split('?')[0].split('/')[0].strip()
        else:
            short_name = user_input.strip()
        
        if not short_name:
            await update.message.reply_text("❌ Неверная ссылка. Попробуй еще раз:")
            return GET_STICKER_SET_LINK
        
        await update.message.reply_text("🔍 Ищу стикерпак...")
        
        # Получаем информацию о стикерпаке
        sticker_set = await context.bot.get_sticker_set(short_name)
        
        context.user_data['original_sticker_set'] = sticker_set
        context.user_data['original_short_name'] = short_name
        
        sticker_info = (
            f"✅ <b>Найден стикерпак!</b>\n\n"
            f"📛 <b>Название:</b> {sticker_set.title}\n"
            f"📊 <b>Стикеров:</b> {len(sticker_set.stickers)}\n\n"
            f"📝 <b>Шаг 2:</b> Введи новое название для копии:"
        )
        
        await update.message.reply_html(sticker_info)
        return GET_NEW_NAME
        
    except Exception as e:
        logger.error(f"Ошибка поиска стикерпака: {e}")
        await update.message.reply_text(f"❌ Не удалось найти стикерпак: {str(e)}")
        return GET_STICKER_SET_LINK

async def get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение нового названия"""
    try:
        new_title = update.message.text.strip()
        
        if not new_title:
            await update.message.reply_text("❌ Название не может быть пустым. Введи название:")
            return GET_NEW_NAME
        
        context.user_data['new_title'] = new_title
        
        await update.message.reply_html(
            "📝 <b>Отличное название!</b>\n\n"
            "🔗 <b>Шаг 3:</b> Введи короткое имя для ссылки:\n\n"
            "💡 <b>Требования:</b>\n"
            "• Латинские буквы (a-z)\n"
            "• Цифры (0-9)\n"
            "• Нижнее подчеркивание (_)\n\n"
            "📝 <b>Примеры:</b>\n"
            "• <code>MyStickers2024</code>\n"
            "• <code>best_pack</code>\n"
            "• <code>cool_stickers</code>\n\n"
            "Введи короткое имя:"
        )
        return GET_NEW_SHORT_NAME
        
    except Exception as e:
        logger.error(f"Ошибка в get_new_name: {e}")
        await update.message.reply_text("❌ Ошибка.")
        return ConversationHandler.END

async def get_new_short_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создание копии стикерпака"""
    try:
        new_short_name = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Простая валидация
        if not new_short_name or len(new_short_name) < 3:
            await update.message.reply_text("❌ Слишком короткое имя. Введи еще раз:")
            return GET_NEW_SHORT_NAME
        
        # Получаем сохраненные данные
        original_sticker_set = context.user_data.get('original_sticker_set')
        new_title = context.user_data.get('new_title')
        
        if not original_sticker_set or not new_title:
            await update.message.reply_text("❌ Данные утеряны. Начни заново: /copy")
            return ConversationHandler.END
        
        await update.message.reply_text("🔄 Создаю копию стикерпака...")
        
        # Берем первый стикер для создания набора
        first_sticker = original_sticker_set.stickers[0]
        
        # Определяем формат
        sticker_format = StickerFormat.STATIC
        if hasattr(first_sticker, 'is_video') and first_sticker.is_video:
            sticker_format = StickerFormat.VIDEO
        elif hasattr(first_sticker, 'is_animated') and first_sticker.is_animated:
            sticker_format = StickerFormat.ANIMATED
        
        # Создаем первый стикер
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
                
                # Прогресс каждые 10 стикеров
                if i % 10 == 0:
                    await update.message.reply_text(f"📦 Добавлено {i}/{len(original_sticker_set.stickers)} стикеров...")
                
                await asyncio.sleep(0.2)  # Задержка между запросами
                
            except Exception as e:
                logger.warning(f"Не удалось добавить стикер {i}: {e}")
                continue
        
        # Ссылка на новый стикерпак
        sticker_link = f"https://t.me/addstickers/{new_short_name}"
        
        success_text = (
            f"🎉 <b>Готово!</b>\n\n"
            f"📛 <b>Название:</b> {new_title}\n"
            f"🔗 <b>Ссылка:</b> {sticker_link}\n"
            f"📊 <b>Скопировано стикеров:</b> {success_count}/{len(original_sticker_set.stickers)}\n\n"
            f"✨ <b>Добавить стикерпак:</b>\n"
            f"<code>{sticker_link}</code>"
        )
        
        await update.message.reply_html(success_text)
        logger.info(f"Успешно создан стикерпак: {new_short_name}")
        
    except Exception as e:
        logger.error(f"Ошибка создания стикерпака: {e}")
        error_msg = str(e)
        if "sticker set name is already occupied" in error_msg:
            await update.message.reply_text("❌ Это короткое имя уже занято. Придумай другое:")
            return GET_NEW_SHORT_NAME
        else:
            await update.message.reply_html(f"❌ <b>Ошибка:</b>\n<code>{error_msg}</code>")
    
    finally:
        context.user_data.clear()
        return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка обычных сообщений"""
    await update.message.reply_html(
        "👋 <b>Бот для копирования стикерпаков</b>\n\n"
        "🚀 <b>Команды:</b>\n"
        "/start - Начать\n"
        "/copy - Копировать стикерпак\n"
        "/help - Помощь\n\n"
        "🔹 <b>Начни с:</b> /copy"
    )

def main():
    """Запуск бота"""
    try:
        if not TOKEN:
            logger.error("Токен не найден!")
            return
        
        logger.info("Запуск бота...")
        
        application = Application.builder().token(TOKEN).build()
        
        # ConversationHandler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("copy", start_copy)],
            states={
                GET_STICKER_SET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sticker_set_link)],
                GET_NEW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_name)],
                GET_NEW_SHORT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_short_name)],
            },
            fallbacks=[CommandHandler("start", start)]
        )
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(conv_handler)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Бот запущен!")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")

if __name__ == "__main__":
    main()