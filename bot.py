import logging
import os
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройки
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Состояния
GET_STICKER_SET_LINK, GET_NEW_NAME, GET_NEW_SHORT_NAME = range(3)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    commands = [
        BotCommand("start", "🔄 Начать"),
        BotCommand("copy", "📦 Копировать стикерпак"),
        BotCommand("help", "ℹ️ Помощь")
    ]
    await context.bot.set_my_commands(commands)
    
    await update.message.reply_html(
        "👋 <b>Бот для копирования стикерпаков</b>\n\n"
        "🚀 <b>Как использовать:</b>\n"
        "1. Отправь /copy\n"
        "2. Пришли ссылку на стикерпак\n"
        "3. Укажи новое название\n"
        "4. Придумай короткое имя\n\n"
        "🔹 <b>Начни:</b> /copy"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help"""
    await update.message.reply_html(
        "📖 <b>Инструкция:</b>\n\n"
        "1. <b>/copy</b> - начать копирование\n"
        "2. <b>Прислать ссылку</b> на стикерпак\n"
        "3. <b>Указать новое название</b>\n"
        "4. <b>Придумать короткое имя</b>\n\n"
        "🚀 <b>Пример ссылки:</b>\n"
        "<code>https://t.me/addstickers/Animals</code>"
    )

async def start_copy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало копирования"""
    context.user_data.clear()
    await update.message.reply_text("📦 Пришли ссылку на стикерпак:")
    return GET_STICKER_SET_LINK

async def get_sticker_set_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение ссылки"""
    try:
        user_input = update.message.text.strip()
        
        # Извлекаем короткое имя
        if "t.me/addstickers/" in user_input:
            short_name = user_input.split("t.me/addstickers/")[-1].split('?')[0].strip()
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
        
        await update.message.reply_html(
            f"✅ <b>Найден стикерпак!</b>\n\n"
            f"📛 <b>Название:</b> {sticker_set.title}\n"
            f"📊 <b>Стикеров:</b> {len(sticker_set.stickers)}\n\n"
            f"📝 Введи новое название:"
        )
        return GET_NEW_NAME
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        return GET_STICKER_SET_LINK

async def get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение нового названия"""
    new_title = update.message.text.strip()
    
    if not new_title:
        await update.message.reply_text("❌ Название не может быть пустым. Введи название:")
        return GET_NEW_NAME
    
    context.user_data['new_title'] = new_title
    await update.message.reply_text("🔗 Введи короткое имя для ссылки (латинские буквы):")
    return GET_NEW_SHORT_NAME

async def get_new_short_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создание копии"""
    try:
        new_short_name = update.message.text.strip()
        user_id = update.effective_user.id
        
        original_sticker_set = context.user_data.get('original_sticker_set')
        new_title = context.user_data.get('new_title')
        
        if not original_sticker_set or not new_title:
            await update.message.reply_text("❌ Данные утеряны. Начни заново: /copy")
            return ConversationHandler.END
        
        await update.message.reply_text("🔄 Создаю копию... Это займет несколько минут.")
        
        # Здесь будет логика создания стикерпака
        # Временно возвращаем сообщение
        await update.message.reply_html(
            f"🎉 <b>Функция копирования в разработке</b>\n\n"
            f"📛 <b>Название:</b> {new_title}\n"
            f"🔗 <b>Короткое имя:</b> {new_short_name}\n"
            f"📊 <b>Исходный стикерпак:</b> {original_sticker_set.title}\n\n"
            f"🚀 <b>Скоро будет доступно!</b>"
        )
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    finally:
        context.user_data.clear()
        return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка обычных сообщений"""
    await update.message.reply_html("👋 Напиши /copy чтобы начать")

def main():
    """Запуск бота"""
    try:
        if not TOKEN:
            logger.error("Токен не найден!")
            return
        
        application = Application.builder().token(TOKEN).build()
        
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
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")

if __name__ == "__main__":
    main()