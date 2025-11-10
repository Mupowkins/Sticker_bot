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
from telegram.constants import StickerFormat
from telegram.error import TelegramError, BadRequest

# ==================== НАСТРОЙКИ ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Состояния для ConversationHandler
GET_STICKER_SET_LINK, GET_NEW_NAME, GET_NEW_SHORT_NAME = range(3)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль
        logging.FileHandler('bot.log')  # Запись в файл
    ]
)
logger = logging.getLogger(__name__)

# ==================== ФУНКЦИИ БОТА ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start
    """
    try:
        user = update.effective_user
        logger.info(f"Пользователь {user.first_name} (ID: {user.id}) запустил бота")
        
        # Устанавливаем команды меню бота
        commands = [
            BotCommand("start", "🔄 Начать работу"),
            BotCommand("copy", "📦 Скопировать стикерпак"),
            BotCommand("cancel", "❌ Отменить операцию"),
            BotCommand("help", "ℹ️ Помощь")
        ]
        await context.bot.set_my_commands(commands)
        
        welcome_text = (
            "👋 <b>Привет, {user_name}!</b>\n\n"
            "Я помогу тебе создавать копии твоих стикерпаков с новыми названиями и ссылками.\n\n"
            "📖 <b>Как использовать:</b>\n"
            "1. Отправь команду /copy\n"
            "2. Пришли ссылку на стикерпак\n"
            "3. Укажи новое название\n"
            "4. Придумай короткое имя для ссылки\n"
            "5. Получи готовый стикерпак!\n\n"
            "🚀 <b>Начнем:</b> Отправь /copy чтобы скопировать стикерпак\n"
            "❓ Нужна помощь? Отправь /help"
        ).format(user_name=user.first_name)
        
        await update.message.reply_html(welcome_text)
        
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /help
    """
    help_text = (
        "📖 <b>Инструкция по использованию бота:</b>\n\n"
        "🔹 <b>Копирование стикерпака:</b>\n"
        "1. Отправь команду /copy\n"
        "2. Пришли ссылку на стикерпак в формате:\n"
        "   <code>https://t.me/addstickers/NameStickerPack</code>\n"
        "3. Укажи новое название для копии\n"
        "4. Придумай короткое имя для ссылки (только латинские буквы, цифры и подчеркивания)\n\n"
        "🔹 <b>Пример короткого имени:</b>\n"
        "   • MyCoolStickers\n"
        "   • best_stickers_2024\n"
        "   • funny_cats_pack\n\n"
        "🔹 <b>Важные ограничения:</b>\n"
        "   • Работает только с твоими стикерпаками\n"
        "   • Короткое имя должно быть уникальным\n"
        "   • Не копируй чужие стикерпаки без разрешения\n\n"
        "🚀 <b>Начать копирование:</b> /copy\n"
        "❌ <b>Отменить операцию:</b> /cancel"
    )
    await update.message.reply_html(help_text)

async def start_copy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало процесса копирования стикерпака
    """
    try:
        user = update.effective_user
        logger.info(f"Пользователь {user.first_name} начал копирование стикерпака")
        
        # Очищаем данные предыдущей операции
        context.user_data.clear()
        
        instruction_text = (
            "📦 <b>Начинаем копирование стикерпака!</b>\n\n"
            "🔗 <b>Шаг 1 из 3:</b> Пришли мне ссылку на стикерпак который хочешь скопировать.\n\n"
            "📝 <b>Формат ссылки:</b>\n"
            "<code>https://t.me/addstickers/NameStickerPack</code>\n\n"
            "💡 <b>Как найти ссылку:</b>\n"
            "1. Открой стикерпак в Telegram\n"
            "2. Нажми на название стикерпака\n"
            "3. Скопируй ссылку\n\n"
            "❌ <b>Отменить:</b> /cancel"
        )
        
        await update.message.reply_html(instruction_text)
        return GET_STICKER_SET_LINK
        
    except Exception as e:
        logger.error(f"Ошибка в start_copy: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
        return ConversationHandler.END

async def get_sticker_set_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение и проверка ссылки на стикерпак
    """
    try:
        user_input = update.message.text.strip()
        logger.info(f"Пользователь отправил ссылку: {user_input}")
        
        # Извлекаем короткое имя из ссылки
        if "t.me/addstickers/" in user_input:
            short_name = user_input.split("t.me/addstickers/")[-1].split('?')[0].split('/')[0].strip()
        else:
            short_name = user_input.strip()
        
        if not short_name:
            await update.message.reply_html(
                "❌ <b>Неверный формат ссылки!</b>\n\n"
                "📝 <b>Правильный формат:</b>\n"
                "<code>https://t.me/addstickers/NameStickerPack</code>\n\n"
                "🔗 <b>Примеры:</b>\n"
                "• <code>https://t.me/addstickers/MyStickers</code>\n"
                "• <code>https://t.me/addstickers/cool_cats</code>\n\n"
                "Попробуй еще раз или отправь /cancel для отмены."
            )
            return GET_STICKER_SET_LINK
        
        # Проверяем существование стикерпака
        await update.message.reply_text("🔍 Ищу стикерпак...")
        
        sticker_set = await context.bot.get_sticker_set(short_name)
        
        # Сохраняем данные для следующих шагов
        context.user_data['original_sticker_set'] = sticker_set
        context.user_data['original_short_name'] = short_name
        
        # Формируем информацию о найденном стикерпаке
        sticker_info = (
            f"✅ <b>Стикерпак найден!</b>\n\n"
            f"📛 <b>Название:</b> {sticker_set.title}\n"
            f"📊 <b>Количество стикеров:</b> {len(sticker_set.stickers)}\n"
            f"🔗 <b>Текущая ссылка:</b> t.me/addstickers/{short_name}\n\n"
        )
        
        # Определяем тип стикеров
        if sticker_set.stickers:
            first_sticker = sticker_set.stickers[0]
            if hasattr(first_sticker, 'is_video') and first_sticker.is_video:
                sticker_info += "🎥 <b>Тип:</b> Видео стикеры\n"
            elif hasattr(first_sticker, 'is_animated') and first_sticker.is_animated:
                sticker_info += "✨ <b>Тип:</b> Анимированные стикеры\n"
            else:
                sticker_info += "🖼️ <b>Тип:</b> Обычные стикеры\n"
        
        sticker_info += (
            "\n📝 <b>Шаг 2 из 3:</b> Придумай и введи новое название для копии стикерпака:\n\n"
            "❌ <b>Отменить:</b> /cancel"
        )
        
        await update.message.reply_html(sticker_info)
        return GET_NEW_NAME
        
    except BadRequest as e:
        logger.warning(f"Стикерпак не найден: {e}")
        await update.message.reply_html(
            "❌ <b>Стикерпак не найден!</b>\n\n"
            "Возможные причины:\n"
            "• Неправильная ссылка\n"
            "• Стикерпак приватный\n"
            "• Стикерпак не существует\n\n"
            "Проверь ссылку и попробуй еще раз или отправь /cancel для отмены."
        )
        return GET_STICKER_SET_LINK
        
    except Exception as e:
        logger.error(f"Ошибка в get_sticker_set_link: {e}")
        await update.message.reply_text("❌ Произошла непредвиденная ошибка. Попробуйте позже.")
        return ConversationHandler.END

async def get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение нового названия для стикерпака
    """
    try:
        new_title = update.message.text.strip()
        
        if not new_title:
            await update.message.reply_text("❌ Название не может быть пустым. Введи название:")
            return GET_NEW_NAME
        
        if len(new_title) > 50:
            await update.message.reply_text("❌ Название слишком длинное (максимум 50 символов). Введи другое название:")
            return GET_NEW_NAME
        
        # Сохраняем новое название
        context.user_data['new_title'] = new_title
        
        instruction_text = (
            "📝 <b>Отличное название!</b>\n\n"
            "🔗 <b>Шаг 3 из 3:</b> Теперь придумай короткое имя для ссылки.\n\n"
            "📋 <b>Требования:</b>\n"
            "• Только латинские буквы (a-z)\n"
            "• Цифры (0-9)\n"
            "• Нижнее подчеркивание (_)\n"
            "• Длина: 5-30 символов\n\n"
            "💡 <b>Примеры:</b>\n"
            "• <code>MyCoolStickers2024</code>\n"
            "• <code>best_stickers_pack</code>\n"
            "• <code>funny_cats_collection</code>\n\n"
            "📝 Введи короткое имя:\n\n"
            "❌ <b>Отменить:</b> /cancel"
        )
        
        await update.message.reply_html(instruction_text)
        return GET_NEW_SHORT_NAME
        
    except Exception as e:
        logger.error(f"Ошибка в get_new_name: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
        return ConversationHandler.END

async def get_new_short_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение короткого имени и создание копии стикерпака
    """
    try:
        new_short_name = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Проверяем короткое имя
        if not new_short_name or len(new_short_name) < 5 or len(new_short_name) > 30:
            await update.message.reply_html(
                "❌ <b>Неверная длина имени!</b>\n\n"
                "📋 <b>Требования:</b>\n"
                "• Длина: 5-30 символов\n\n"
                "📝 Введи короткое имя еще раз:\n\n"
                "❌ <b>Отменить:</b> /cancel"
            )
            return GET_NEW_SHORT_NAME
        
        if not all(c.isalnum() or c == '_' for c in new_short_name):
            await update.message.reply_html(
                "❌ <b>Неверные символы!</b>\n\n"
                "📋 <b>Можно использовать:</b>\n"
                "• Латинские буквы (a-z, A-Z)\n"
                "• Цифры (0-9)\n"
                "• Нижнее подчеркивание (_)\n\n"
                "📝 Введи короткое имя еще раз:\n\n"
                "❌ <b>Отменить:</b> /cancel"
            )
            return GET_NEW_SHORT_NAME
        
        # Получаем сохраненные данные
        original_sticker_set = context.user_data.get('original_sticker_set')
        new_title = context.user_data.get('new_title')
        
        if not original_sticker_set or not new_title:
            await update.message.reply_text("❌ Данные утеряны. Начни заново с /copy")
            return ConversationHandler.END
        
        # Начинаем процесс создания копии
        await update.message.reply_text("🔄 Начинаю создание копии стикерпака...")
        
        # Определяем формат стикеров
        first_sticker = original_sticker_set.stickers[0]
        sticker_format = StickerFormat.STATIC
        
        if hasattr(first_sticker, 'is_video') and first_sticker.is_video:
            sticker_format = StickerFormat.VIDEO
        elif hasattr(first_sticker, 'is_animated') and first_sticker.is_animated:
            sticker_format = StickerFormat.ANIMATED
        
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
                
                # Отправляем прогресс каждые 5 стикеров
                if i % 5 == 0 or i == total_stickers:
                    progress_text = f"📦 Добавлено {i}/{total_stickers} стикеров..."
                    await update.message.reply_text(progress_text)
                
                # Небольшая задержка чтобы не превысить лимиты API
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Не удалось добавить стикер {i}: {e}")
                continue
        
        # Формируем ссылку на новый стикерпак
        sticker_link = f"https://t.me/addstickers/{new_short_name}"
        
        success_text = (
            f"🎉 <b>Стикерпак успешно скопирован!</b>\n\n"
            f"📛 <b>Название:</b> {new_title}\n"
            f"🔗 <b>Ссылка:</b> {sticker_link}\n"
            f"📊 <b>Стикеров:</b> {len(original_sticker_set.stickers)}\n\n"
            f"✨ <b>Теперь ты можешь добавить его к себе:</b>\n"
            f"<code>{sticker_link}</code>\n\n"
            f"🚀 <b>Скопировать еще один стикерпак?</b> Отправь /copy"
        )
        
        await update.message.reply_html(success_text)
        
        # Логируем успешное создание
        logger.info(f"Создан новый стикерпак: {new_short_name} для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в get_new_short_name: {e}")
        await update.message.reply_html(
            "❌ <b>Произошла ошибка при создании стикерпака!</b>\n\n"
            f"<code>Ошибка: {str(e)}</code>\n\n"
            "🚀 <b>Попробуй еще раз:</b> /copy"
        )
    
    finally:
        # Очищаем данные пользователя
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отмена текущей операции
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} отменил операцию")
    
    context.user_data.clear()
    
    await update.message.reply_html(
        "❌ <b>Операция отменена.</b>\n\n"
        "🚀 <b>Начать заново:</b> /copy\n"
        "❓ <b>Помощь:</b> /help"
    )
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка обычных сообщений
    """
    user = update.effective_user
    message_text = (
        "👋 <b>Привет!</b> Я бот для копирования стикерпаков.\n\n"
        "📖 <b>Основные команды:</b>\n"
        "/start - Начать работу\n"
        "/copy - Скопировать стикерпак\n"
        "/help - Помощь и инструкция\n\n"
        "🚀 <b>Начни с команды</b> /copy"
    )
    await update.message.reply_html(message_text)

def main():
    """
    Основная функция запуска бота
    """
    try:
        # Проверяем что токен установлен
        if not TOKEN:
            logger.error("Токен бота не найден! Убедитесь что переменная TELEGRAM_TOKEN установлена.")
            return
        
        logger.info("Запуск бота...")
        
        # Создаем приложение
        application = Application.builder().token(TOKEN).build()
        
        # ConversationHandler для копирования стикерпаков
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("copy", start_copy)],
            states={
                GET_STICKER_SET_LINK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_sticker_set_link)
                ],
                GET_NEW_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_name)
                ],
                GET_NEW_SHORT_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_short_name)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                CommandHandler("start", start),
                CommandHandler("help", help_command)
            ],
            allow_reentry=True
        )
        
        # Обычные команды
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        
        # ConversationHandler (должен быть добавлен после обычных команд)
        application.add_handler(conv_handler)
        
        # Обработчик для любых сообщений
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_message
        ))
        
        # Запускаем бота
        logger.info("Бот запущен и готов к работе!")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")

if __name__ == "__main__":
    main()
