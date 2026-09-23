"""Teste pentru contractele API folosite de agentul Dev."""

import pytest
from pydantic import ValidationError

from lora_api.schemas import FinanceTransactionRequest, UniversityScheduleRequest


def test_finance_transaction_defaults_and_type() -> None:
    payload = FinanceTransactionRequest(amount=25.5)
    assert payload.type == "expense"
    assert payload.category == ""


def test_finance_transaction_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError):
        FinanceTransactionRequest(amount=0)


def test_schedule_contract_accepts_valid_entry() -> None:
    payload = UniversityScheduleRequest(
        subject_name="Programare",
        day_of_week=1,
        start_time="10:00",
        end_time="12:00",
        week_type="odd",
    )
    assert payload.class_type == "curs"


def test_schedule_contract_rejects_invalid_day_and_type() -> None:
    with pytest.raises(ValidationError):
        UniversityScheduleRequest(
            subject_name="Programare",
            day_of_week=8,
            start_time="10:00",
            end_time="12:00",
        )
