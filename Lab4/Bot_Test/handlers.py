"""Обработчики сообщений Telegram-бота."""
import logging
from datetime import datetime
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from llm_client import LLMClient
from calendar_client import CalendarClient
from schema import LLMResponseModel
from config import Config

logger = logging.getLogger(__name__)


class MessageHandler:
    """Класс для обработки сообщений пользователя."""
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.calendar_client = CalendarClient()
        self.confidence_threshold = Config.LLM_CONFIDENCE_THRESHOLD
        # Хранилище для контекста уточнений (user_id -> состояние)
        self.clarification_context: dict = {}
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Основной обработчик сообщений пользователя.
        
        Args:
            update: Обновление от Telegram
            context: Контекст бота
        """
        user_id = update.effective_user.id
        user_message = update.message.text.strip()
        
        logger.info(f"Получено сообщение от пользователя {user_id}: {user_message}")
        
        # Проверяем, есть ли активный контекст уточнений
        if user_id in self.clarification_context:
            await self._handle_clarification_response(update, context, user_message)
            return
        
        # Отправляем сообщение в LLM
        llm_response = self.llm_client.parse_user_message(user_message)
        
        if not llm_response:
            await update.message.reply_text(
                "Извините, произошла ошибка при обработке вашего запроса. "
                "Попробуйте переформулировать."
            )
            return
        
        # Обрабатываем ответ LLM
        await self._process_llm_response(update, context, llm_response)
    
    async def _process_llm_response(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        llm_response: LLMResponseModel
    ) -> None:
        """
        Обрабатывает ответ от LLM и выполняет соответствующее действие.
        
        Args:
            update: Обновление от Telegram
            context: Контекст бота
            llm_response: Ответ от LLM
        """
        user_id = update.effective_user.id
        
        # Если нужны уточнения
        if llm_response.clarify.needed and llm_response.clarify.questions:
            self.clarification_context[user_id] = {
                "intent": llm_response.intent,
                "slots": llm_response.slots.model_dump(),
                "questions": llm_response.clarify.questions,
                "current_question_index": 0
            }
            first_question = llm_response.clarify.questions[0]
            await update.message.reply_text(first_question)
            return
        
        # Если низкая уверенность, запрашиваем подтверждение
        if llm_response.confidence < self.confidence_threshold:
            confirmation_text = self._format_confirmation(llm_response)
            self.clarification_context[user_id] = {
                "intent": llm_response.intent,
                "slots": llm_response.slots.model_dump(),
                "waiting_confirmation": True
            }
            await update.message.reply_text(
                f"{confirmation_text}\n\nПравильно ли я понял? (Да / Нет)"
            )
            return
        
        # Выполняем действие в зависимости от intent
        if llm_response.intent == "create":
            await self._handle_create(update, context, llm_response)
        elif llm_response.intent == "list":
            await self._handle_list(update, context, llm_response)
        elif llm_response.intent == "delete":
            await self._handle_delete(update, context, llm_response)
        elif llm_response.intent == "unknown":
            await update.message.reply_text(
                "Извините, я не понял вашу команду. "
                "Попробуйте сказать, например:\n"
                "- Создать событие: 'назначь встречу на завтра в 15:00'\n"
                "- Показать события: 'покажи события на 27 ноября'\n"
                "- Удалить событие: 'удали встречу с Вадимом'"
            )
    
    async def _handle_clarification_response(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_message: str
    ) -> None:
        """
        Обрабатывает ответ пользователя на уточняющие вопросы.
        
        Args:
            update: Обновление от Telegram
            context: Контекст бота
            user_message: Ответ пользователя
        """
        user_id = update.effective_user.id
        context_data = self.clarification_context[user_id]
        
        # Проверяем, ждем ли мы подтверждения удаления
        if context_data.get("waiting_delete_confirmation"):
            user_message_lower = user_message.lower().strip()
            if user_message_lower in ["да", "yes", "давай", "ок", "хорошо"]:
                event_id = context_data.get("event_id")
                if event_id:
                    success = self.calendar_client.delete_event(event_id)
                    if success:
                        await update.message.reply_text("✅ Событие удалено.")
                    else:
                        await update.message.reply_text("❌ Не удалось удалить событие.")
                del self.clarification_context[user_id]
                return
            elif user_message_lower in ["нет", "no", "не", "неправильно"]:
                del self.clarification_context[user_id]
                await update.message.reply_text(
                    "Хорошо, событие не будет удалено."
                )
                return
            else:
                await update.message.reply_text(
                    "Пожалуйста, ответьте 'Да' или 'Нет'."
                )
                return
        
        # Проверяем, ждем ли мы подтверждения
        if context_data.get("waiting_confirmation"):
            user_message_lower = user_message.lower().strip()
            if user_message_lower in ["да", "yes", "давай", "ок", "хорошо"]:
                # Подтверждение получено, выполняем действие
                slots = context_data["slots"]
                intent = context_data["intent"]
                
                # Создаем временный LLMResponseModel для выполнения действия
                from schema import SlotsModel, ClarifyModel
                temp_response = LLMResponseModel(
                    intent=intent,
                    confidence=1.0,
                    slots=SlotsModel(**slots),
                    clarify=ClarifyModel(needed=False, questions=[])
                )
                
                del self.clarification_context[user_id]
                
                if intent == "create":
                    await self._handle_create(update, context, temp_response)
                elif intent == "list":
                    await self._handle_list(update, context, temp_response)
                elif intent == "delete":
                    await self._handle_delete(update, context, temp_response)
            elif user_message_lower in ["нет", "no", "не", "неправильно"]:
                del self.clarification_context[user_id]
                await update.message.reply_text(
                    "Понятно. Пожалуйста, переформулируйте ваш запрос более подробно."
                )
            else:
                await update.message.reply_text(
                    "Пожалуйста, ответьте 'Да' или 'Нет'."
                )
            return
        
        # Обрабатываем уточняющие вопросы
        questions = context_data.get("questions", [])
        current_index = context_data.get("current_question_index", 0)
        
        if current_index < len(questions) - 1:
            # Есть еще вопросы
            context_data["current_question_index"] = current_index + 1
            next_question = questions[current_index + 1]
            await update.message.reply_text(next_question)
        else:
            # Все вопросы заданы, повторно отправляем в LLM с уточненными данными
            # Формируем новое сообщение с исходным запросом и ответами
            # (упрощенная реализация - можно улучшить)
            del self.clarification_context[user_id]
            await update.message.reply_text(
                "Спасибо за уточнения. Обрабатываю ваш запрос..."
            )
            # Повторно обрабатываем исходное сообщение
            # (в реальной реализации нужно сохранять исходное сообщение)
            await update.message.reply_text(
                "Пожалуйста, повторите ваш запрос с учетом уточнений."
            )
    
    async def _handle_create(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        llm_response: LLMResponseModel
    ) -> None:
        """Обрабатывает создание события."""
        slots = llm_response.slots
        
        if not slots.title or not slots.start:
            await update.message.reply_text(
                "Для создания события необходимо указать название и время начала. "
                "Пожалуйста, уточните эти данные."
            )
            return
        
        # Создаем событие
        event = self.calendar_client.create_event(
            title=slots.title,
            start_datetime=slots.start,
            end_datetime=slots.end,
            description=slots.description,
            location=slots.location,
            participants=slots.participants
        )
        
        if event:
            start_time = self._format_datetime_for_user(slots.start)
            message = (
                f"✅ Событие создано!\n\n"
                f"📅 {slots.title}\n"
                f"🕐 {start_time}\n"
            )
            if slots.location:
                message += f"📍 {slots.location}\n"
            if slots.participants:
                message += f"👥 Участники: {', '.join(slots.participants)}\n"
            message += f"\nID события: {event['id']}"
            if event.get('htmlLink'):
                message += f"\n🔗 {event['htmlLink']}"
            
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(
                "❌ Не удалось создать событие. Проверьте правильность данных и попробуйте снова."
            )
    
    async def _handle_list(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        llm_response: LLMResponseModel
    ) -> None:
        """Обрабатывает просмотр событий."""
        slots = llm_response.slots
        
        # Определяем дату для просмотра
        target_date = None
        if slots.date:
            target_date = slots.date
        elif slots.start:
            # Извлекаем дату из start
            try:
                dt = datetime.fromisoformat(slots.start.replace("Z", "+00:00"))
                target_date = dt.strftime("%Y-%m-%d")
            except:
                pass
        
        if not target_date:
            await update.message.reply_text(
                "Пожалуйста, укажите дату для просмотра событий. "
                "Например: 'покажи события на 27 ноября' или '/view 2025-11-27'"
            )
            return
        
        # Получаем события
        events = self.calendar_client.list_events(target_date)
        
        if not events:
            await update.message.reply_text(
                f"📅 На {self._format_date_for_user(target_date)} нет запланированных событий."
            )
            return
        
        # Формируем сообщение со списком событий
        message = f"📅 События на {self._format_date_for_user(target_date)}:\n\n"
        
        for i, event in enumerate(events, 1):
            summary = event.get('summary', 'Без названия')
            start = event.get('start', {})
            start_time = start.get('dateTime', start.get('date', ''))
            
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M")
                except:
                    time_str = start_time
            else:
                time_str = "?"
            
            event_id = event.get('id', '')
            message += f"{i}. 🕐 {time_str} - {summary}\n   ID: {event_id[:8]}...\n\n"
        
        await update.message.reply_text(message)
    
    async def _handle_delete(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        llm_response: LLMResponseModel
    ) -> None:
        """Обрабатывает удаление события."""
        slots = llm_response.slots
        
        # Если указан event_id, удаляем напрямую
        if slots.event_id:
            success = self.calendar_client.delete_event(slots.event_id)
            if success:
                await update.message.reply_text("✅ Событие удалено.")
            else:
                await update.message.reply_text("❌ Не удалось удалить событие.")
            return
        
        # Ищем события по названию и дате
        if not slots.title:
            await update.message.reply_text(
                "Для удаления события необходимо указать его название. "
                "Пожалуйста, уточните."
            )
            return
        
        # Определяем дату
        target_date = None
        if slots.date:
            target_date = slots.date
        elif slots.start:
            try:
                dt = datetime.fromisoformat(slots.start.replace("Z", "+00:00"))
                target_date = dt.strftime("%Y-%m-%d")
            except:
                pass
        
        if not target_date:
            # Используем сегодняшнюю дату
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        # Ищем события
        matching_events = self.calendar_client.find_events_by_title_and_date(
            slots.title, target_date
        )
        
        if not matching_events:
            await update.message.reply_text(
                f"Не найдено событий с названием '{slots.title}' на {self._format_date_for_user(target_date)}."
            )
            return
        
        if len(matching_events) == 1:
            # Одно событие - показываем и запрашиваем подтверждение
            event = matching_events[0]
            event_id = event.get('id')
            summary = event.get('summary', 'Без названия')
            start = event.get('start', {})
            start_time = start.get('dateTime', start.get('date', ''))
            
            message = (
                f"Найдено событие:\n\n"
                f"📅 {summary}\n"
            )
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    message += f"🕐 {dt.strftime('%Y-%m-%d %H:%M')}\n"
                except:
                    message += f"🕐 {start_time}\n"
            
            message += "\nУдалить это событие? (Да / Нет)"
            
            # Сохраняем контекст для подтверждения
            user_id = update.effective_user.id
            self.clarification_context[user_id] = {
                "waiting_delete_confirmation": True,
                "event_id": event_id
            }
            
            await update.message.reply_text(message)
        else:
            # Несколько событий - показываем список
            message = f"Найдено несколько событий с названием '{slots.title}':\n\n"
            for i, event in enumerate(matching_events, 1):
                summary = event.get('summary', 'Без названия')
                event_id = event.get('id')
                message += f"{i}. {summary} (ID: {event_id[:8]}...)\n"
            message += "\nПожалуйста, укажите ID события для удаления."
            
            await update.message.reply_text(message)
    
    def _format_confirmation(self, llm_response: LLMResponseModel) -> str:
        """Форматирует текст подтверждения для пользователя."""
        intent_map = {
            "create": "создать событие",
            "list": "показать события",
            "delete": "удалить событие"
        }
        
        action = intent_map.get(llm_response.intent, "выполнить действие")
        slots = llm_response.slots
        
        parts = [f"Я правильно понял, что нужно {action}?"]
        
        if slots.title:
            parts.append(f"Название: {slots.title}")
        if slots.start:
            parts.append(f"Время начала: {self._format_datetime_for_user(slots.start)}")
        if slots.end:
            parts.append(f"Время окончания: {self._format_datetime_for_user(slots.end)}")
        if slots.location:
            parts.append(f"Место: {slots.location}")
        if slots.participants:
            parts.append(f"Участники: {', '.join(slots.participants)}")
        
        return "\n".join(parts)
    
    def _format_datetime_for_user(self, dt_str: str) -> str:
        """Форматирует дату/время для отображения пользователю."""
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return dt_str
    
    def _format_date_for_user(self, date_str: str) -> str:
        """Форматирует дату для отображения пользователю."""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except:
            return date_str
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start."""
        message = (
            "👋 Привет! Я бот-планировщик для Google Calendar.\n\n"
            "Я могу помочь вам:\n"
            "✅ Создавать события (например: 'назначь встречу на завтра в 15:00')\n"
            "📅 Просматривать события (например: 'покажи события на 27 ноября')\n"
            "❌ Удалять события (например: 'удали встречу с Вадимом')\n\n"
            "Просто напишите мне вашу задачу естественным языком!"
        )
        await update.message.reply_text(message)
    
    async def handle_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /add."""
        # Извлекаем текст после команды
        command_text = update.message.text.replace("/add", "").strip()
        if not command_text:
            await update.message.reply_text(
                "Использование: /add <текст>\n"
                "Пример: /add назначь встречу на завтра в 15:00"
            )
            return
        
        # Обрабатываем как обычное сообщение
        await self.handle_message(update, context)
    
    async def handle_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /view."""
        # Извлекаем дату
        command_text = update.message.text.replace("/view", "").strip()
        if not command_text:
            await update.message.reply_text(
                "Использование: /view YYYY-MM-DD\n"
                "Пример: /view 2025-11-27"
            )
            return
        
        # Формируем сообщение для LLM
        update.message.text = f"покажи события на {command_text}"
        await self.handle_message(update, context)
    
    async def handle_delete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /delete."""
        # Извлекаем идентификатор
        command_text = update.message.text.replace("/delete", "").strip()
        if not command_text:
            await update.message.reply_text(
                "Использование: /delete <event_id|название>\n"
                "Пример: /delete abc123 или /delete встреча с Вадимом"
            )
            return
        
        # Если это похоже на event_id (короткая строка), используем напрямую
        if len(command_text) < 50 and not " " in command_text:
            # Пытаемся удалить по ID
            success = self.calendar_client.delete_event(command_text)
            if success:
                await update.message.reply_text("✅ Событие удалено.")
            else:
                await update.message.reply_text("❌ Не удалось удалить событие. Проверьте ID.")
            return
        
        # Иначе обрабатываем как обычное сообщение
        update.message.text = f"удали {command_text}"
        await self.handle_message(update, context)

