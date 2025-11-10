import logging
import os
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    commands = [
        BotCommand("start", "🔄 Начать работу"),
        BotCommand("copy", "📦 Скопировать стикерпак"),
        BotCommand("help", "ℹ️ Помощь")
    ]
    await context.bot.set_my_commands(commands)
    
    await update.message.reply_html(
        "👋 <b>Привет! Я бот для копирования стикерпаков</b>\n\n"
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
            f"📝 Введи новое название для копии:"
        )
        return GET_NEW_NAME
        
    except Exception as e:
        logger.error(f"Ошибка поиска стикерпака: {e}")
        await update.message.reply_text(f"❌ Не удалось найти стикерпак. Проверь ссылку.")
        return GET_STICKER_SET_LINK

async def get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение нового названия"""
    new_title = update.message.text.strip()
    
    if not new_title:
        await update.message.reply_text("❌ Название не может быть пустым. Введи название:")
        return GET_NEW_NAME
    
    context.user_data['new_title'] = new_title
    await update.message.reply_text("🔗 Введи короткое имя для ссылки (только латинские буквы и цифры):")
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
        
        await update.message.reply_text("🔄 Начинаю копирование... Это займет несколько минут.")
        
        # Создаем новый стикерпак
        first_sticker = original_sticker_set.stickers[0]
        
        # Определяем тип стикеров
        sticker_format = StickerFormat.STATIC
        if hasattr(first_sticker, 'is_animated') and first_sticker.is_animated:
            sticker_format = StickerFormat.ANIMATED
        elif hasattr(first_sticker, 'is_video') and first_sticker.is_video:
            sticker_format = StickerFormat.VIDEO
        
        # Создаем InputSticker для первого стикера
        input_sticker = InputSticker(
            sticker=first_sticker.file_id,
            emoji_list=first_sticker.emoji if hasattr(first_sticker, 'emoji') else ['🙂']
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
        added_count = 1
        total_stickers = len(original_sticker_set.stickers)
        
        for i, sticker in enumerate(original_sticker_set.stickers[1:], 2):
            try:
                input_sticker = InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=sticker.emoji if hasattr(sticker, 'emoji') else ['🙂']
                )
                
                await context.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_short_name,
                    sticker=input_sticker
                )
                added_count += 1
                
                # Прогресс каждые 10 стикеров
                if i % 10 == 0:
                    await update.message.reply_text(f"📦 Скопировано {i}/{total_stickers} стикеров...")
                    
            except Exception as e:
                logger.warning(f"Не удалось добавить стикер {i}: {e}")
                continue
        
        # Ссылка на новый стикерпак
        sticker_link = f"https://t.me/addstickers/{new_short_name}"
        
        await update.message.reply_html(
            f"🎉 <b>Стикерпак успешно скопирован!</b>\n\n"
            f"📛 <b>Название:</b> {new_title}\n"
            f"🔗 <b>Ссылка:</b> {sticker_link}\n"
            f"📊 <b>Стикеров:</b> {added_count}/{total_stickers}\n\n"
            f"✨ <b>Добавить к себе:</b>\n"
            f"<code>{sticker_link}</code>"
        )
        
        logger.info(f"Успешно создан стикерпак: {new_short_name}")
        
    except Exception as e:
        logger.error(f"Ошибка создания стикерпака: {e}")
        error_msg = str(e)
        if "sticker set name is already occupied" in error_msg:
            await update.message.reply_text("❌ Это имя уже занято. Придумай другое:")
            return GET_NEW_SHORT_NAME
        else:
            await update.message.reply_text(f"❌ Ошибка при создании: {error_msg}")
    
    finally:
        context.user_data.clear()
        return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка обычных сообщений"""
    await update.message.reply_html("👋 Напиши /copy чтобы начать копирование стикерпаков")

def main():
    """Запуск бота"""
    try:
        if not TOKEN:
            logger.error("Токен не найден! Проверь переменную TELEGRAM_TOKEN")
            return
        
        logger.info("Запуск бота...")
        
        application = Application.builder().token(TOKEN).build()
        
        # ConversationHandler для копирования стикерпаков
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
        
        logger.info("✅ Бот запущен и готов к работе!")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()