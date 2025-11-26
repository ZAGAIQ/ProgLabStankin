"""Точка входа приложения - запуск Telegram-бота."""
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import InvalidToken

from config import Config
from handlers import MessageHandler as BotMessageHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, Config.LOG_LEVEL.upper())
)
logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок."""
    logger.error(f"Ошибка при обработке обновления: {context.error}", exc_info=context.error)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке вашего запроса. Попробуйте позже."
        )


def main():
    """Основная функция запуска бота."""
    # Валидация конфигурации
    try:
        Config.validate()
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Ошибка конфигурации: {e}")
        print(f"\n❌ Ошибка конфигурации: {e}\n")
        print("Пожалуйста, проверьте:")
        print("1. Существует ли файл .env с необходимыми переменными")
        print("2. Существует ли файл credentials.json")
        print("3. См. README.md для подробных инструкций")
        return
    
    # Создаем приложение
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    # Создаем обработчик сообщений
    bot_message_handler = BotMessageHandler()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", bot_message_handler.handle_start))
    application.add_handler(CommandHandler("add", bot_message_handler.handle_add))
    application.add_handler(CommandHandler("view", bot_message_handler.handle_view))
    application.add_handler(CommandHandler("delete", bot_message_handler.handle_delete_command))
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback=bot_message_handler.handle_message))
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Запуск Telegram-бота...")
    print("\n✅ Бот запущен! Нажмите Ctrl+C для остановки.\n")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя")
        print("\n👋 Бот остановлен.\n")
    except InvalidToken as e:
        logger.error(f"Ошибка токена Telegram: {e}")
        print(f"\n❌ Ошибка токена Telegram: {e}\n")
        print("Пожалуйста, проверьте:")
        print("1. Файл .env существует и содержит правильный TELEGRAM_TOKEN")
        print("2. Токен получен от @BotFather в Telegram")
        print("3. Токен не содержит лишних пробелов или символов")
        print("\nСм. README.md для подробных инструкций по настройке.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ Критическая ошибка: {e}\n")


if __name__ == "__main__":
    main()

