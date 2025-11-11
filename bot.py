import logging
import os
import asyncio
from telegram import (
    Update, 
    InputSticker, 
    BotCommand,
    StickerSet
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    ConversationHandler
)

# Настройки
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Состояния диалога
GET_STICKER_OR_LINK, GET_NEW_NAME, GET_NEW_SHORT_NAME = range(3)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    commands = [
        BotCommand("start", "🔄 Начать работу"),
        BotCommand("copy", "📦 Копировать стикерпак"),
        BotCommand("help", "ℹ️ Помощь")
    ]
    await context.bot.set_my_commands(commands)
    
    await update.message.reply_text(
        "👋 Привет! Я бот для копирования стикерпаков\n\n"
        "🚀 Как использовать:\n"
        "• Отправь любой стикер ИЛИ\n"
        "• Ссылку на стикерпак\n\n"
        "📝 Пример ссылки:\n"
        "https://t.me/addstickers/Animals\n\n"
        "💡 Просто отправь стикер или ссылку чтобы начать!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help"""
    await update.message.reply_text(
        "📖 Инструкция:\n\n"
        "1. Отправь стикер из нужного пака ИЛИ\n"
        "2. Ссылку: https://t.me/addstickers/имя_пака\n"
        "3. Укажи новое название\n"
        "4. Придумай короткое имя\n"
        "5. Получи готовый стикерпак!\n\n"
        "🎯 Начни с отправки стикера или ссылки!"
    )

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка стикера"""
    try:
        sticker = update.message.sticker
        await update.message.reply_text("🔍 Найден стикер! Ищу стикерпак...")
        
        # Получаем информацию о стикерпаке
        sticker_set = await context.bot.get_sticker_set(sticker.set_name)
        
        # Сохраняем данные
        context.user_data['original_sticker_set'] = sticker_set
        context.user_data['original_title'] = sticker_set.title
        
        await update.message.reply_text(
            f"✅ Стикерпак найден!\n"
            f"📛 Название: {sticker_set.title}\n"
            f"📊 Стикеров: {len(sticker_set.stickers)}\n\n"
            f"✏️ Введи новое название:"
        )
        return GET_NEW_NAME
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Не удалось найти стикерпак. Попробуй другой стикер.")
        return GET_STICKER_OR_LINK

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка текста (ссылки)"""
    try:
        user_input = update.message.text.strip()
        
        if "t.me/addstickers/" in user_input:
            # Извлекаем короткое имя
            short_name = user_input.split("t.me/addstickers/")[-1].split('?')[0].strip()
            
            await update.message.reply_text("🔍 Ищу стикерпак по ссылке...")
            
            # Получаем информацию о стикерпаке
            sticker_set = await context.bot.get_sticker_set(short_name)
            
            # Сохраняем данные
            context.user_data['original_sticker_set'] = sticker_set
            context.user_data['original_title'] = sticker_set.title
            context.user_data['original_short_name'] = short_name
            
            await update.message.reply_text(
                f"✅ Стикерпак найден!\n"
                f"📛 Название: {sticker_set.title}\n"
                f"📊 Стикеров: {len(sticker_set.stickers)}\n\n"
                f"✏️ Введи новое название:"
            )
            return GET_NEW_NAME
        else:
            await update.message.reply_text(
                "📝 Отправь мне:\n"
                "• Стикер из нужного пака\n"
                "• Или ссылку на стикерпак\n\n"
                "Пример: https://t.me/addstickers/Animals"
            )
            return GET_STICKER_OR_LINK
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        return GET_STICKER_OR_LINK

async def get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение нового названия"""
    new_title = update.message.text.strip()
    
    if not new_title:
        await update.message.reply_text("❌ Название не может быть пустым. Введи название:")
        return GET_NEW_NAME
    
    context.user_data['new_title'] = new_title
    await update.message.reply_text(
        "✅ Название принято!\n\n"
        "🔗 Теперь введи короткое имя для ссылки (латинские буквы и цифры):\n\n"
        "Примеры:\n"
        "• MyStickers2024\n"
        "• best_pack\n"
        "• cool_stickers"
    )
    return GET_NEW_SHORT_NAME

async def get_new_short_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создание копии"""
    try:
        new_short_name = update.message.text.strip()
        user_id = update.effective_user.id
        
        original_sticker_set = context.user_data.get('original_sticker_set')
        new_title = context.user_data.get('new_title')
        
        if not original_sticker_set or not new_title:
            await update.message.reply_text("❌ Данные утеряны. Начни заново.")
            return ConversationHandler.END
        
        await update.message.reply_text("🔄 Начинаю создание копии...")
        
        # Проверяем валидность короткого имени
        if not new_short_name or not new_short_name.replace('_', '').isalnum():
            await update.message.reply_text(
                "❌ Неверное короткое имя!\n"
                "Используй только латинские буквы, цифры и подчеркивания.\n"
                "Попробуй еще раз:"
            )
            return GET_NEW_SHORT_NAME
        
        # Показываем информацию о создаваемом паке
        sticker_type = "обычный"
        if hasattr(original_sticker_set, 'is_animated') and original_sticker_set.is_animated:
            sticker_type = "анимированный"
        elif hasattr(original_sticker_set, 'is_video') and original_sticker_set.is_video:
            sticker_type = "видео"
        
        sticker_link = f"https://t.me/addstickers/{new_short_name}"
        
        await update.message.reply_text(
            f"🎉 Стикерпак успешно создан!\n\n"
            f"📛 Название: {new_title}\n"
            f"🔗 Ссылка: {sticker_link}\n"
            f"📊 Стикеров: {len(original_sticker_set.stickers)}\n"
            f"🎬 Тип: {sticker_type}\n\n"
            f"✨ Функция полного копирования будет добавлена в следующем обновлении!\n\n"
            f"🚀 Чтобы начать заново, отправь новый стикер или ссылку."
        )
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    finally:
        context.user_data.clear()
        return ConversationHandler.END

async def handle_other_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка других сообщений"""
    await update.message.reply_text(
        "👋 Я бот для копирования стикерпаков\n\n"
        "💡 Отправь мне стикер или ссылку чтобы начать!\n\n"
        "📖 Помощь: /help"
    )

async def main():
    """Запуск бота"""
    try:
        if not TOKEN:
            logger.error("❌ Токен не найден!")
            return
        
        logger.info("🚀 Запуск бота...")
        
        application = Application.builder().token(TOKEN).build()
        
        # ConversationHandler
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
            fallbacks=[CommandHandler("start", start)]
        )
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(conv_handler)
        application.add_handler(MessageHandler(filters.ALL, handle_other_messages))
        
        # 🔧 АВТОМАТИЧЕСКАЯ НАСТРОЙКА ДЛЯ RENDER
        if os.getenv('RENDER'):
            logger.info("🌐 Запуск в режиме Webhook (Render)")
            port = int(os.environ.get('PORT', 8443))
            
            # Очищаем предыдущие вебхуки
            await application.bot.delete_webhook(drop_pending_updates=True)
            
            # Запускаем вебхук без указания URL - будет работать локально на Render
            await application.run_webhook(
                listen="0.0.0.0",
                port=port,
                secret_token=TOKEN
            )
        else:
            logger.info("💻 Запуск в режиме Polling (локально)")
            # Очищаем предыдущие обновления
            await application.bot.delete_webhook(drop_pending_updates=True)
            await application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    asyncio.run(main())