"""Клиент для работы с LLM через Open Router API."""
import json
import logging
from typing import Optional
from pathlib import Path
import requests
from config import Config
from schema import LLMResponseModel

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент для взаимодействия с LLM через Open Router."""
    
    def __init__(self):
        self.api_key = Config.OPENROUTER_API_KEY
        self.api_url = Config.OPENROUTER_API_URL
        self.model = Config.LLM_MODEL
        
    def _load_prompt_template(self) -> dict:
        """Загружает шаблон промпта из файла."""
        try:
            import json as json_module
            prompt_path = Path("prompts/prompt_templates.json")
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return json_module.load(f)
            else:
                logger.warning("Файл prompts/prompt_templates.json не найден, используем дефолтный промпт")
                return self._get_default_prompt()
        except Exception as e:
            logger.error(f"Ошибка загрузки промпта: {e}, используем дефолтный")
            return self._get_default_prompt()
    
    def _get_default_prompt(self) -> dict:
        """Возвращает дефолтный промпт, если файл не найден."""
        return {
            "system": """Вы — JSON-генератор для Telegram-бота планировщика. 
Ваша задача — анализировать естественные фразы пользователя на русском языке и возвращать строго структурированный JSON.

ПРАВИЛА:
1. На каждый запрос возвращайте ТОЛЬКО JSON в указанном формате, без дополнительного текста.
2. Все даты и время в формате ISO8601 с часовым поясом Europe/Moscow (+03:00).
3. Если недостаточно данных для выполнения действия — верните clarify.needed=true и заполните questions конкретными уточняющими вопросами.
4. confidence — ваша уверенность в распознавании намерения (0.0-1.0).
5. Для intent используйте: "create" (создать событие), "list" (показать события), "delete" (удалить событие), "unknown" (не удалось распознать).
6. ВАЖНО: Участники (participants), описание (description) и место (location) являются ОПЦИОНАЛЬНЫМИ полями. НЕ спрашивайте об участниках, если пользователь их не упомянул. Событие может быть создано без участников. Спрашивайте только о критически важных полях: название (title) и время начала (start) для создания события.

ФОРМАТ ОТВЕТА:
{
  "intent": "create" | "list" | "delete" | "unknown",
  "confidence": 0.0-1.0,
  "slots": {
    "title": "название события",
    "start": "2025-11-27T15:00:00+03:00",
    "end": "2025-11-27T16:00:00+03:00",
    "date": "2025-11-27",
    "participants": ["имя1", "имя2"],
    "description": "описание",
    "location": "место",
    "event_id": null
  },
  "clarify": {
    "needed": false,
    "questions": []
  }
}""",
            "examples": [
                {
                    "user": "назначь на завтра встречу в 15:00 с вадимом",
                    "response": {
                        "intent": "create",
                        "confidence": 0.95,
                        "slots": {
                            "title": "Встреча с Вадимом",
                            "start": "2025-11-27T15:00:00+03:00",
                            "end": "2025-11-27T16:00:00+03:00",
                            "participants": ["Вадим"]
                        },
                        "clarify": {"needed": False, "questions": []}
                    }
                }
            ]
        }
    
    def parse_user_message(self, user_message: str) -> Optional[LLMResponseModel]:
        """
        Отправляет сообщение пользователя в LLM и возвращает распарсенный ответ.
        
        Args:
            user_message: Сообщение пользователя на русском языке
            
        Returns:
            LLMResponseModel или None в случае ошибки
        """
        try:
            prompt_data = self._load_prompt_template()
            system_prompt = prompt_data.get("system", "")
            examples = prompt_data.get("examples", [])
            
            # Формируем промпт с примерами
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Добавляем примеры
            for example in examples[:3]:  # Берем первые 3 примера
                messages.append({
                    "role": "user",
                    "content": example.get("user", "")
                })
                messages.append({
                    "role": "assistant",
                    "content": json.dumps(example.get("response", {}), ensure_ascii=False)
                })
            
            # Добавляем текущий запрос пользователя
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Отправляем запрос в Open Router
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/your-repo",
                "X-Title": "Telegram Calendar Bot"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3
            }
            
            # Некоторые модели могут не поддерживать response_format
            # Попробуем добавить, если модель поддерживает
            try:
                payload["response_format"] = {"type": "json_object"}
            except:
                pass
            
            logger.info(f"Отправка запроса в LLM для сообщения: {user_message[:50]}...")
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                logger.error("Пустой ответ от LLM")
                return None
            
            # Пытаемся извлечь JSON из ответа
            json_str = self._extract_json(content)
            if not json_str:
                logger.error(f"Не удалось извлечь JSON из ответа: {content}")
                return None
            
            # Парсим и валидируем через Pydantic
            parsed_data = json.loads(json_str)
            llm_response = LLMResponseModel(**parsed_data)
            
            logger.info(f"Успешно распознано намерение: {llm_response.intent}, confidence: {llm_response.confidence}")
            return llm_response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к LLM API: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от LLM: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при работе с LLM: {e}")
            return None
    
    def _extract_json(self, text: str) -> Optional[str]:
        """
        Извлекает JSON из текста ответа LLM.
        
        Args:
            text: Текст ответа от LLM
            
        Returns:
            JSON строка или None
        """
        # Пытаемся найти JSON в тексте
        text = text.strip()
        
        # Если текст начинается с {, пытаемся найти закрывающую скобку
        if text.startswith("{"):
            try:
                # Находим последнюю закрывающую скобку
                brace_count = 0
                end_idx = -1
                for i, char in enumerate(text):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i
                            break
                
                if end_idx > 0:
                    json_str = text[:end_idx + 1]
                    # Проверяем, что это валидный JSON
                    json.loads(json_str)
                    return json_str
            except:
                pass
        
        # Если не получилось, пытаемся найти JSON между ```json и ```
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        
        # Если не получилось, пытаемся найти JSON между ``` и ```
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("{") and part.endswith("}"):
                    try:
                        json.loads(part)
                        return part
                    except:
                        continue
        
        # Последняя попытка - весь текст
        try:
            json.loads(text)
            return text
        except:
            return None

