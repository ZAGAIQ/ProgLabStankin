"""Конфигурация приложения - загрузка переменных окружения."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()


class Config:
    """Класс для хранения конфигурации приложения."""
    
    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    
    # Open Router / LLM
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    LLM_MODEL: str = os.getenv("LLM_MODEL", "mistralai/mistral-7b-instruct:free")
    LLM_CONFIDENCE_THRESHOLD: float = float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.80"))
    
    # Google Calendar
    GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    GOOGLE_TOKEN_PATH: str = os.getenv("GOOGLE_TOKEN_PATH", "./token.json")
    GOOGLE_SCOPES: list = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events"
    ]
    
    # Временная зона
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")
    DEFAULT_EVENT_DURATION_MIN: int = int(os.getenv("DEFAULT_EVENT_DURATION_MIN", "60"))
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """Проверяет наличие обязательных переменных окружения."""
        if not cls.TELEGRAM_TOKEN or cls.TELEGRAM_TOKEN == "your_telegram_token_here":
            raise ValueError(
                "TELEGRAM_TOKEN не установлен в .env или имеет значение по умолчанию.\n"
                "Пожалуйста, создайте файл .env на основе .env.example и заполните реальный токен от @BotFather"
            )
        if not cls.OPENROUTER_API_KEY or cls.OPENROUTER_API_KEY == "your_openrouter_api_key_here":
            raise ValueError(
                "OPENROUTER_API_KEY не установлен в .env или имеет значение по умолчанию.\n"
                "Пожалуйста, получите API ключ на https://openrouter.ai/ и добавьте его в .env"
            )
        if not Path(cls.GOOGLE_CREDENTIALS_PATH).exists():
            raise FileNotFoundError(
                f"Файл credentials.json не найден по пути: {cls.GOOGLE_CREDENTIALS_PATH}\n"
                "Пожалуйста, создайте OAuth 2.0 клиент в Google Cloud Console и скачайте credentials.json"
            )
        return True

