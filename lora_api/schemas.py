"""Modele Pydantic pentru payload-uri API recurente."""

from typing import Literal
from pydantic import BaseModel, Field


class FinanceTransactionRequest(BaseModel):
    amount: float = Field(gt=0)
    category: str = ""
    description: str = ""
    type: Literal["expense", "income"] = "expense"


class UniversityScheduleRequest(BaseModel):
    subject_name: str = Field(min_length=1)
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    room: str | None = None
    class_type: Literal["curs", "seminar", "laborator", "curs+seminars"] = "curs"
    week_type: Literal["odd", "even", "both"] = "both"
