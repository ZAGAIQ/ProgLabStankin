"""Клиент для работы с Google Calendar API."""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pathlib import Path
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import Config

logger = logging.getLogger(__name__)


class CalendarClient:
    """Клиент для взаимодействия с Google Calendar."""
    
    def __init__(self):
        self.credentials_path = Config.GOOGLE_CREDENTIALS_PATH
        self.token_path = Config.GOOGLE_TOKEN_PATH
        self.scopes = Config.GOOGLE_SCOPES
        self.timezone = Config.TIMEZONE
        self.default_duration_min = Config.DEFAULT_EVENT_DURATION_MIN
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Аутентификация в Google Calendar API."""
        creds = None
        
        # Проверяем, есть ли сохраненный токен
        if Path(self.token_path).exists():
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
                logger.info("Загружен сохраненный токен")
            except Exception as e:
                logger.warning(f"Ошибка загрузки токена: {e}")
        
        # Если нет валидных учетных данных, запрашиваем авторизацию
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Токен обновлен")
                except Exception as e:
                    logger.error(f"Ошибка обновления токена: {e}")
                    creds = None
            
            if not creds:
                if not Path(self.credentials_path).exists():
                    raise FileNotFoundError(
                        f"Файл credentials.json не найден по пути: {self.credentials_path}\n"
                        "Пожалуйста, создайте OAuth 2.0 клиент в Google Cloud Console и скачайте credentials.json"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.scopes
                )
                # Используем локальный сервер для OAuth
                creds = flow.run_local_server(port=0)
                logger.info("Выполнена новая авторизация")
            
            # Сохраняем токен для следующего запуска
            Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
            logger.info(f"Токен сохранен в {self.token_path}")
        
        # Создаем сервис для работы с календарем
        try:
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Успешное подключение к Google Calendar API")
        except Exception as e:
            logger.error(f"Ошибка создания сервиса Google Calendar: {e}")
            raise
    
    def create_event(
        self,
        title: str,
        start_datetime: str,
        end_datetime: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        participants: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Создает событие в Google Calendar.
        
        Args:
            title: Название события
            start_datetime: Дата и время начала в ISO8601 формате
            end_datetime: Дата и время окончания в ISO8601 формате (опционально)
            description: Описание события
            location: Место проведения
            participants: Список участников (имена или email)
            
        Returns:
            Словарь с данными созданного события или None в случае ошибки
        """
        try:
            # Парсим дату начала
            start_dt = self._parse_datetime(start_datetime)
            
            # Если дата окончания не указана, добавляем дефолтную длительность
            if end_datetime:
                end_dt = self._parse_datetime(end_datetime)
            else:
                end_dt = start_dt + timedelta(minutes=self.default_duration_min)
            
            # Формируем список участников (attendees)
            attendees = []
            if participants:
                for participant in participants:
                    # Если это email, добавляем как email, иначе как имя
                    if "@" in participant:
                        attendees.append({"email": participant})
                    else:
                        # Если нет email, добавляем в описание
                        if description:
                            description += f"\nУчастники: {', '.join(participants)}"
                        else:
                            description = f"Участники: {', '.join(participants)}"
            
            # Формируем тело события
            event_body = {
                'summary': title,
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': self.timezone,
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': self.timezone,
                },
            }
            
            if description:
                event_body['description'] = description
            
            if location:
                event_body['location'] = location
            
            if attendees:
                event_body['attendees'] = attendees
            
            # Создаем событие
            event = self.service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()
            
            logger.info(f"Создано событие: {title} (ID: {event.get('id')})")
            return {
                'id': event.get('id'),
                'summary': event.get('summary'),
                'start': event.get('start'),
                'end': event.get('end'),
                'htmlLink': event.get('htmlLink')
            }
            
        except HttpError as e:
            logger.error(f"Ошибка Google Calendar API при создании события: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании события: {e}")
            return None
    
    def list_events(self, date: str) -> List[Dict]:
        """
        Получает список событий на указанную дату.
        
        Args:
            date: Дата в формате YYYY-MM-DD
            
        Returns:
            Список событий
        """
        try:
            # Парсим дату
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            
            # Начало дня (00:00:00)
            time_min = datetime.combine(date_obj.date(), datetime.min.time())
            time_min = time_min.replace(tzinfo=self._get_timezone())
            
            # Конец дня (23:59:59)
            time_max = datetime.combine(date_obj.date(), datetime.max.time())
            time_max = time_max.replace(tzinfo=self._get_timezone())
            # Устанавливаем 23:59:59
            time_max = time_max.replace(hour=23, minute=59, second=59)
            
            # Запрашиваем события
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Найдено {len(events)} событий на {date}")
            
            return events
            
        except HttpError as e:
            logger.error(f"Ошибка Google Calendar API при получении событий: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении событий: {e}")
            return []
    
    def delete_event(self, event_id: str) -> bool:
        """
        Удаляет событие по ID.
        
        Args:
            event_id: ID события в Google Calendar
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            logger.info(f"Событие {event_id} удалено")
            return True
            
        except HttpError as e:
            logger.error(f"Ошибка Google Calendar API при удалении события: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при удалении события: {e}")
            return False
    
    def find_events_by_title_and_date(self, title: str, date: str) -> List[Dict]:
        """
        Находит события по названию и дате.
        
        Args:
            title: Часть названия события
            date: Дата в формате YYYY-MM-DD
            
        Returns:
            Список найденных событий
        """
        events = self.list_events(date)
        matching_events = []
        
        title_lower = title.lower()
        for event in events:
            event_title = event.get('summary', '').lower()
            if title_lower in event_title:
                matching_events.append(event)
        
        return matching_events
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        """
        Парсит строку даты/времени в объект datetime.
        
        Args:
            dt_str: Дата/время в ISO8601 формате
            
        Returns:
            Объект datetime с временной зоной
        """
        # Убираем Z и заменяем на +00:00 если нужно
        dt_str = dt_str.replace("Z", "+00:00")
        
        # Парсим ISO8601
        try:
            dt = datetime.fromisoformat(dt_str)
        except ValueError:
            # Если не получилось, пытаемся другой формат
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
        
        # Если нет временной зоны, добавляем московскую
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self._get_timezone())
        
        return dt
    
    def _get_timezone(self):
        """Возвращает объект временной зоны."""
        try:
            # Python 3.9+ имеет встроенный zoneinfo
            from zoneinfo import ZoneInfo
            return ZoneInfo(self.timezone)
        except ImportError:
            # Fallback на pytz для старых версий Python
            import pytz
            return pytz.timezone(self.timezone)

