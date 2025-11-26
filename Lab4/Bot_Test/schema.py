"""Pydantic-схемы для валидации JSON-ответов от LLM."""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ClarifyModel(BaseModel):
    """Модель для уточняющих вопросов."""
    needed: bool = Field(default=False, description="Нужно ли уточнение")
    questions: List[str] = Field(default_factory=list, description="Список уточняющих вопросов")


class SlotsModel(BaseModel):
    """Модель для слотов (параметров) намерения."""
    title: Optional[str] = Field(default=None, description="Название события")
    start: Optional[str] = Field(default=None, description="Дата и время начала в ISO8601 с часовым поясом")
    end: Optional[str] = Field(default=None, description="Дата и время окончания в ISO8601 с часовым поясом")
    date: Optional[str] = Field(default=None, description="Дата для просмотра/удаления в формате YYYY-MM-DD")
    participants: Optional[List[str]] = Field(default=None, description="Список участников")
    description: Optional[str] = Field(default=None, description="Описание события")
    location: Optional[str] = Field(default=None, description="Место проведения")
    event_id: Optional[str] = Field(default=None, description="ID события для удаления")
    
    @field_validator("start", "end", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        """Валидация формата даты/времени."""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                # Проверяем, что это валидный ISO8601 формат
                datetime.fromisoformat(v.replace("Z", "+00:00"))
                return v
            except ValueError:
                raise ValueError(f"Неверный формат даты/времени: {v}")
        return v


class LLMResponseModel(BaseModel):
    """Модель для ответа от LLM."""
    intent: Literal["create", "list", "delete", "unknown"] = Field(
        description="Намерение пользователя"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, 
        description="Уверенность LLM в распознавании намерения (0.0-1.0)"
    )
    slots: SlotsModel = Field(default_factory=SlotsModel, description="Параметры намерения")
    clarify: ClarifyModel = Field(default_factory=ClarifyModel, description="Уточняющие вопросы")
    
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        """Валидация confidence."""
        if not isinstance(v, (int, float)):
            raise ValueError("confidence должен быть числом")
        return float(v)

