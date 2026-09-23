"""Contracte de date partajate între agent, API și module.

Aceste tipuri documentează forma payload-urilor; validarea runtime rămâne în API.
"""

from typing import Literal, NotRequired, TypedDict


class FinanceTransactionInput(TypedDict):
    amount: float
    category: NotRequired[str]
    description: NotRequired[str]
    type: NotRequired[Literal["expense", "income"]]


class UniversityScheduleInput(TypedDict):
    subject_name: str
    day_of_week: int
    start_time: str
    end_time: str
    room: NotRequired[str | None]
    class_type: NotRequired[Literal["curs", "seminar", "laborator", "curs+seminars"]]
    week_type: NotRequired[Literal["odd", "even", "both"]]
