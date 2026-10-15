"""Validated commands shared by Telegram, Mini App, and the AI interpreter."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Date and time must include a timezone offset")
    return value


class CreateProject(StrictModel):
    name: str = Field(min_length=1, max_length=200)


class CreateTask(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    notes: str | None = None
    due_at: datetime | None = None
    project_id: str | None = None

    @field_validator("due_at")
    @classmethod
    def validate_due(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value else None


class CreateCalendarEntry(StrictModel):
    kind: Literal["event", "reminder"]
    title: str = Field(min_length=1, max_length=300)
    starts_at: datetime
    ends_at: datetime | None = None
    notes: str | None = None
    alert_offsets_minutes: list[int] = Field(default_factory=list)
    followup_evening: bool = False

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_time(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value else None

    @field_validator("alert_offsets_minutes")
    @classmethod
    def validate_offsets(cls, values: list[int]) -> list[int]:
        if any(value < 0 or value > 10080 for value in values):
            raise ValueError("Alert offsets must be between 0 and 10080 minutes")
        return sorted(set(values), reverse=True)


class LogExpense(StrictModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="RON", min_length=3, max_length=3)
    category: str | None = None
    category_override: bool = False
    expected_merchant_category: str | None = None
    merchant: str | None = None
    description: str | None = None
    spent_at: datetime

    @field_validator("spent_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return _aware(value)


class LogIncome(StrictModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="RON", min_length=3, max_length=3)
    category: str | None = None
    source: str | None = None
    description: str | None = None
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return _aware(value)


class MealItem(StrictModel):
    name: str = Field(min_length=1)
    grams: Decimal | None = Field(default=None, gt=0)
    calories: Decimal | None = Field(default=None, ge=0)
    protein_g: Decimal | None = Field(default=None, ge=0)
    carbs_g: Decimal | None = Field(default=None, ge=0)
    fat_g: Decimal | None = Field(default=None, ge=0)
    nutrition_provider: str | None = Field(default=None, max_length=100)
    nutrition_source_id: str | None = Field(default=None, max_length=100)
    nutrition_source_title: str | None = Field(default=None, max_length=200)
    nutrition_source_url: str | None = Field(default=None, max_length=500)


class LogMeal(StrictModel):
    eaten_at: datetime
    description: str | None = None
    items: list[MealItem] = Field(min_length=1)
    estimate_source: Literal["text", "photo", "manual"] = "text"
    photo_ref: str | None = None

    @field_validator("eaten_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return _aware(value)


class WorkoutExercise(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    sets: int | None = Field(default=None, ge=1, le=100)
    reps: int | None = Field(default=None, ge=1, le=1000)
    weight_kg: Decimal | None = Field(default=None, ge=0, le=1000)


class LogWorkout(StrictModel):
    started_at: datetime
    duration_minutes: int = Field(gt=0, le=1440)
    activity: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    exercises: list[WorkoutExercise] = Field(default_factory=list)

    @field_validator("started_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return _aware(value)


class LogHealth(StrictModel):
    log_date: date
    sleep_hours: Decimal | None = Field(default=None, ge=0, le=24)
    sleep_quality: Literal["great", "good", "neutral", "bad", "terrible"] | None = None
    water_ml_delta: int | None = Field(default=None, ge=0)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=500)
    cigarettes_delta: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def has_value(self) -> "LogHealth":
        if not any(value is not None for value in (
            self.sleep_hours, self.sleep_quality, self.water_ml_delta,
            self.weight_kg, self.cigarettes_delta, self.notes,
        )):
            raise ValueError("At least one health value is required")
        return self


class RescheduleEntry(StrictModel):
    entry_id: UUID
    starts_at: datetime
    expected_version: int

    @field_validator("starts_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return _aware(value)


class CompleteEntry(StrictModel):
    entry_id: UUID
    expected_version: int


class CompleteTask(StrictModel):
    task_id: UUID
    expected_version: int


COMMAND_MODELS: dict[str, type[StrictModel]] = {
    "create_project": CreateProject,
    "create_task": CreateTask,
    "create_calendar_entry": CreateCalendarEntry,
    "log_expense": LogExpense,
    "log_income": LogIncome,
    "log_meal": LogMeal,
    "log_workout": LogWorkout,
    "log_health": LogHealth,
    "reschedule_entry": RescheduleEntry,
    "complete_entry": CompleteEntry,
    "complete_task": CompleteTask,
}


class Command(StrictModel):
    type: str
    data: dict[str, Any]

    def payload(self) -> StrictModel:
        try:
            model = COMMAND_MODELS[self.type]
        except KeyError as exc:
            raise ValueError(f"Unsupported command: {self.type}") from exc
        return model.model_validate(self.data)


class ActionResult(StrictModel):
    status: Literal["saved", "already_done", "needs_input", "failed", "deferred"]
    command_type: str
    entity_id: str | None = None
    entity_type: str | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
