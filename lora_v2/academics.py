"""Versioned university records. Obsidian and n8n remain external, untouched sources."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

import asyncpg
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AcademicKind = Literal["subject", "schedule", "attendance", "grade", "exam", "vacation"]


class AcademicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Subject(AcademicModel):
    name: str = Field(min_length=1, max_length=200)
    professor: str | None = None
    credits: int | None = Field(default=None, ge=0, le=60)
    is_active: bool = True


class Schedule(AcademicModel):
    title: str = Field(min_length=1, max_length=200)
    subject_id: uuid.UUID | None = None
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    week_type: Literal["both", "odd", "even"] = "both"
    class_type: str | None = None
    room: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def times_are_ordered(self) -> "Schedule":
        if self.end_time <= self.start_time:
            raise ValueError("Ora de final trebuie să fie după început")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("Intervalul de valabilitate este invalid")
        return self


class Attendance(AcademicModel):
    subject_id: uuid.UUID | None = None
    schedule_rule_id: uuid.UUID | None = None
    class_date: date
    attended: bool
    notes: str | None = None


class Grade(AcademicModel):
    subject_id: uuid.UUID | None = None
    label: str | None = None
    value: Decimal | None = Field(default=None, ge=0, le=10)
    recorded_at: datetime | None = None

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value and value.tzinfo is None:
            raise ValueError("Data trebuie să includă fusul orar")
        return value


class Exam(AcademicModel):
    subject_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    exam_type: str | None = None
    room: str | None = None
    notes: str | None = None

    @field_validator("starts_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Data trebuie să includă fusul orar")
        return value


class Vacation(AcademicModel):
    name: str | None = None
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "Vacation":
        if self.ends_on < self.starts_on:
            raise ValueError("Vacanța se termină înainte să înceapă")
        return self


MODELS: dict[AcademicKind, type[AcademicModel]] = {
    "subject": Subject, "schedule": Schedule, "attendance": Attendance,
    "grade": Grade, "exam": Exam, "vacation": Vacation,
}


async def _validate_links(conn: asyncpg.Connection, owner_id: int, payload: AcademicModel) -> None:
    subject_id = getattr(payload, "subject_id", None)
    rule_id = getattr(payload, "schedule_rule_id", None)
    if subject_id and not await conn.fetchval(
        "SELECT 1 FROM academic_subjects WHERE id=$1 AND owner_id=$2", subject_id, owner_id
    ):
        raise ValueError("Materia nu există")
    if rule_id and not await conn.fetchval(
        "SELECT 1 FROM academic_schedule_rules WHERE id=$1 AND owner_id=$2", rule_id, owner_id
    ):
        raise ValueError("Cursul nu există")


async def list_academics(pool: asyncpg.Pool, owner_id: int) -> dict[str, Any]:
    async with pool.acquire() as conn:
        subjects = await conn.fetch(
            "SELECT id,name,professor,credits,is_active,version FROM academic_subjects WHERE owner_id=$1 ORDER BY name",
            owner_id,
        )
        schedules = await conn.fetch(
            """SELECT id,subject_id,title,day_of_week,start_time,end_time,week_type,class_type,
            room,valid_from,valid_until,is_active,version FROM academic_schedule_rules
            WHERE owner_id=$1 ORDER BY day_of_week,start_time""",
            owner_id,
        )
        attendance = await conn.fetch(
            """SELECT id,subject_id,schedule_rule_id,class_date,attended,notes,version
            FROM academic_attendance WHERE owner_id=$1 AND deleted_at IS NULL
            ORDER BY class_date DESC LIMIT 200""",
            owner_id,
        )
        grades = await conn.fetch(
            """SELECT id,subject_id,label,value,recorded_at,version FROM academic_grades
            WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY recorded_at DESC NULLS LAST LIMIT 200""",
            owner_id,
        )
        exams = await conn.fetch(
            """SELECT id,subject_id,title,starts_at,exam_type,room,notes,version
            FROM academic_exams WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY starts_at""",
            owner_id,
        )
        vacations = await conn.fetch(
            """SELECT id,name,starts_on,ends_on,version FROM academic_vacations
            WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY starts_on""",
            owner_id,
        )
        semester = await conn.fetchrow(
            "SELECT semester_start,semester_end,version FROM academic_semesters WHERE owner_id=$1", owner_id
        )
    return {
        "subjects": [dict(row) for row in subjects],
        "schedules": [dict(row) for row in schedules],
        "attendance": [dict(row) for row in attendance],
        "grades": [dict(row) for row in grades],
        "exams": [dict(row) for row in exams],
        "vacations": [dict(row) for row in vacations],
        "semester": dict(semester) if semester else None,
    }


async def write_academic(
    pool: asyncpg.Pool, owner_id: int, kind: AcademicKind,
    data: dict[str, Any], entity_id: uuid.UUID | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    payload = MODELS[kind].model_validate(data)
    item_id = entity_id or uuid.uuid4()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _validate_links(conn, owner_id, payload)
            if entity_id is None:
                if kind == "subject" and isinstance(payload, Subject):
                    row = await conn.fetchrow(
                        """INSERT INTO academic_subjects(id,owner_id,name,professor,credits,is_active)
                        VALUES ($1,$2,$3,$4,$5,$6) RETURNING version""",
                        item_id, owner_id, payload.name, payload.professor, payload.credits, payload.is_active,
                    )
                elif kind == "schedule" and isinstance(payload, Schedule):
                    row = await conn.fetchrow(
                        """INSERT INTO academic_schedule_rules(id,owner_id,subject_id,title,day_of_week,start_time,
                        end_time,week_type,class_type,room,valid_from,valid_until,is_active)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING version""",
                        item_id, owner_id, payload.subject_id, payload.title, payload.day_of_week,
                        payload.start_time, payload.end_time, payload.week_type, payload.class_type,
                        payload.room, payload.valid_from, payload.valid_until, payload.is_active,
                    )
                elif kind == "attendance" and isinstance(payload, Attendance):
                    row = await conn.fetchrow(
                        """INSERT INTO academic_attendance(id,owner_id,subject_id,schedule_rule_id,class_date,attended,notes)
                        VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING version""",
                        item_id, owner_id, payload.subject_id, payload.schedule_rule_id,
                        payload.class_date, payload.attended, payload.notes,
                    )
                elif kind == "grade" and isinstance(payload, Grade):
                    row = await conn.fetchrow(
                        """INSERT INTO academic_grades(id,owner_id,subject_id,label,value,recorded_at)
                        VALUES ($1,$2,$3,$4,$5,$6) RETURNING version""",
                        item_id, owner_id, payload.subject_id, payload.label, payload.value, payload.recorded_at,
                    )
                elif kind == "exam" and isinstance(payload, Exam):
                    row = await conn.fetchrow(
                        """INSERT INTO academic_exams(id,owner_id,subject_id,title,starts_at,exam_type,room,notes)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING version""",
                        item_id, owner_id, payload.subject_id, payload.title, payload.starts_at,
                        payload.exam_type, payload.room, payload.notes,
                    )
                elif kind == "vacation" and isinstance(payload, Vacation):
                    row = await conn.fetchrow(
                        """INSERT INTO academic_vacations(id,owner_id,name,starts_on,ends_on)
                        VALUES ($1,$2,$3,$4,$5) RETURNING version""",
                        item_id, owner_id, payload.name, payload.starts_on, payload.ends_on,
                    )
                else:
                    raise ValueError("Tip academic necunoscut")
            else:
                if expected_version is None:
                    raise ValueError("Versiunea este necesară pentru editare")
                if kind == "subject" and isinstance(payload, Subject):
                    row = await conn.fetchrow(
                        """UPDATE academic_subjects SET name=$4,professor=$5,credits=$6,is_active=$7,version=version+1
                        WHERE id=$1 AND owner_id=$2 AND version=$3 RETURNING version""",
                        item_id, owner_id, expected_version, payload.name, payload.professor,
                        payload.credits, payload.is_active,
                    )
                elif kind == "schedule" and isinstance(payload, Schedule):
                    row = await conn.fetchrow(
                        """UPDATE academic_schedule_rules SET subject_id=$4,title=$5,day_of_week=$6,
                        start_time=$7,end_time=$8,week_type=$9,class_type=$10,room=$11,
                        valid_from=$12,valid_until=$13,is_active=$14,version=version+1
                        WHERE id=$1 AND owner_id=$2 AND version=$3 RETURNING version""",
                        item_id, owner_id, expected_version, payload.subject_id, payload.title,
                        payload.day_of_week, payload.start_time, payload.end_time, payload.week_type,
                        payload.class_type, payload.room, payload.valid_from, payload.valid_until,
                        payload.is_active,
                    )
                elif kind == "attendance" and isinstance(payload, Attendance):
                    row = await conn.fetchrow(
                        """UPDATE academic_attendance SET subject_id=$4,schedule_rule_id=$5,class_date=$6,
                        attended=$7,notes=$8,version=version+1 WHERE id=$1 AND owner_id=$2
                        AND version=$3 AND deleted_at IS NULL RETURNING version""",
                        item_id, owner_id, expected_version, payload.subject_id, payload.schedule_rule_id,
                        payload.class_date, payload.attended, payload.notes,
                    )
                elif kind == "grade" and isinstance(payload, Grade):
                    row = await conn.fetchrow(
                        """UPDATE academic_grades SET subject_id=$4,label=$5,value=$6,recorded_at=$7,
                        version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3
                        AND deleted_at IS NULL RETURNING version""",
                        item_id, owner_id, expected_version, payload.subject_id, payload.label,
                        payload.value, payload.recorded_at,
                    )
                elif kind == "exam" and isinstance(payload, Exam):
                    row = await conn.fetchrow(
                        """UPDATE academic_exams SET subject_id=$4,title=$5,starts_at=$6,exam_type=$7,
                        room=$8,notes=$9,version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3
                        AND deleted_at IS NULL RETURNING version""",
                        item_id, owner_id, expected_version, payload.subject_id, payload.title,
                        payload.starts_at, payload.exam_type, payload.room, payload.notes,
                    )
                elif kind == "vacation" and isinstance(payload, Vacation):
                    row = await conn.fetchrow(
                        """UPDATE academic_vacations SET name=$4,starts_on=$5,ends_on=$6,version=version+1
                        WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version""",
                        item_id, owner_id, expected_version, payload.name, payload.starts_on, payload.ends_on,
                    )
                else:
                    raise ValueError("Tip academic necunoscut")
            if not row:
                raise ValueError("Elementul a fost schimbat între timp")
    return {"id": str(item_id), "version": row["version"]}


async def delete_academic(
    pool: asyncpg.Pool, owner_id: int, kind: AcademicKind,
    entity_id: uuid.UUID, expected_version: int,
) -> dict[str, Any]:
    statements = {
        "subject": "UPDATE academic_subjects SET is_active=false,version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3 RETURNING version",
        "schedule": "UPDATE academic_schedule_rules SET is_active=false,version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3 RETURNING version",
        "attendance": "UPDATE academic_attendance SET deleted_at=now(),version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
        "grade": "UPDATE academic_grades SET deleted_at=now(),version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
        "exam": "UPDATE academic_exams SET deleted_at=now(),version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
        "vacation": "UPDATE academic_vacations SET deleted_at=now(),version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
    }
    async with pool.acquire() as conn:
        version = await conn.fetchval(statements[kind], entity_id, owner_id, expected_version)
    if not version:
        raise ValueError("Elementul a fost schimbat între timp")
    return {"id": str(entity_id), "version": version}


async def set_semester(
    pool: asyncpg.Pool, owner_id: int,
    start: date, end: date | None, expected_version: int | None,
) -> dict[str, int]:
    if end and end < start:
        raise ValueError("Semestrul se termină înainte să înceapă")
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchval(
                "SELECT version FROM academic_semesters WHERE owner_id=$1 FOR UPDATE", owner_id
            )
            if current is None:
                if expected_version is not None:
                    raise ValueError("Semestrul nu există")
                version = await conn.fetchval(
                    """INSERT INTO academic_semesters(owner_id,semester_start,semester_end)
                    VALUES ($1,$2,$3) RETURNING version""",
                    owner_id, start, end,
                )
            else:
                if expected_version != current:
                    raise ValueError("Semestrul a fost schimbat între timp")
                version = await conn.fetchval(
                    """UPDATE academic_semesters SET semester_start=$2,semester_end=$3,
                    version=version+1,updated_at=now() WHERE owner_id=$1 RETURNING version""",
                    owner_id, start, end,
                )
    return {"version": version}
