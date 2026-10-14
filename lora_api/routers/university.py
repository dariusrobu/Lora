from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from fastapi import HTTPException
from lora_api.schemas import UniversityScheduleRequest

router = APIRouter(prefix="/api/university", tags=["university"])


@router.post("/subjects")
async def create_subject(data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    pool = await get_pool()
    subject_id = await q.add_subject(pool, name, data.get("credits"), data.get("professor"), data.get("total_classes", 0))
    return {"id": subject_id, "status": "created"}


@router.put("/subjects/{subject_id}")
async def update_subject(subject_id: int, data: dict, user=Depends(get_current_user)):
    """Actualizează metadatele unei materii fără a modifica istoricul academic."""
    import db.queries.university as q
    allowed = {"name", "professor", "credits", "total_classes", "total_seminars", "min_attendance_pct"}
    updates = {key: data[key] for key in allowed if key in data}
    if "name" in updates and not str(updates["name"]).strip():
        raise HTTPException(status_code=422, detail="name is required")
    if not updates:
        raise HTTPException(status_code=422, detail="Nu există câmpuri de actualizat")
    pool = await get_pool()
    await q.update_subject(pool, subject_id, **updates)
    return {"id": subject_id, "status": "updated"}


@router.delete("/subjects/{subject_id}")
async def delete_subject(subject_id: int, user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    await q.delete_subject(pool, subject_id)
    return {"id": subject_id, "status": "deleted"}


@router.post("/grades")
async def create_grade(data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    subject_id = data.get("subject_id")
    if not subject_id or data.get("grade") is None:
        raise HTTPException(status_code=422, detail="subject_id and grade are required")
    grade_id = await q.add_grade_with_weight(pool, int(subject_id), float(data["grade"]), data.get("grade_type", "exam"), data.get("weight"), data.get("assessment_title"), data.get("assessment_date"), data.get("notes"))
    return {"id": grade_id, "status": "created"}

@router.put("/grades/{grade_id}")
async def update_grade(grade_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    allowed = {"grade", "grade_type", "weight", "assessment_title", "assessment_date", "notes"}
    updates = {k: data[k] for k in allowed if k in data}
    if not updates: raise HTTPException(status_code=422, detail="Nu există câmpuri de actualizat")
    pool = await get_pool(); await q.update_grade(pool, grade_id, **updates)
    return {"id": grade_id, "status": "updated"}

@router.delete("/grades/{grade_id}")
async def delete_grade(grade_id: int, user=Depends(get_current_user)):
    import db.queries.university as q
    await q.delete_grade(await get_pool(), grade_id)
    return {"id": grade_id, "status": "deleted"}


@router.post("/exams")
async def create_exam(data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    if not data.get("subject_id") or not data.get("exam_date"):
        raise HTTPException(status_code=422, detail="subject_id and exam_date are required")
    from datetime import date
    try:
        exam_date = date.fromisoformat(str(data["exam_date"]))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="exam_date must use YYYY-MM-DD") from exc
    exam_id = await q.add_exam(pool, int(data["subject_id"]), exam_date, data.get("exam_type", "final"), data.get("room"), data.get("notes"))
    return {"id": exam_id, "status": "created"}

@router.put("/exams/{exam_id}")
async def update_exam(exam_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    allowed = {"exam_date", "exam_type", "room", "notes"}
    updates = {k: data[k] for k in allowed if k in data}
    if not updates: raise HTTPException(status_code=422, detail="Nu există câmpuri de actualizat")
    await q.update_exam(await get_pool(), exam_id, **updates)
    return {"id": exam_id, "status": "updated"}

@router.delete("/exams/{exam_id}")
async def delete_exam(exam_id: int, user=Depends(get_current_user)):
    import db.queries.university as q
    await q.delete_exam(await get_pool(), exam_id)
    return {"id": exam_id, "status": "deleted"}


@router.post("/attendance")
async def create_attendance(data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    from datetime import date
    pool = await get_pool()
    if not data.get("subject_id") or data.get("attended") is None or not data.get("class_date"):
        raise HTTPException(status_code=422, detail="subject_id, attended and class_date are required")
    try:
        class_date = date.fromisoformat(str(data["class_date"]))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="class_date must use YYYY-MM-DD") from exc
    class_type = data.get("class_type", "curs")
    if class_type not in {"curs", "seminar"}:
        raise HTTPException(status_code=422, detail="class_type trebuie să fie curs sau seminar")
    try:
        attendance_id = await q.log_attendance(pool, int(data["subject_id"]), bool(data["attended"]), class_date, data.get("notes"), class_type)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": attendance_id, "status": "created"}

@router.put("/attendance/{attendance_id}")
async def update_attendance(attendance_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    allowed = {"attended", "class_date", "notes"}
    updates = {k: data[k] for k in allowed if k in data}
    if not updates: raise HTTPException(status_code=422, detail="Nu există câmpuri de actualizat")
    await q.update_attendance(await get_pool(), attendance_id, **updates)
    return {"id": attendance_id, "status": "updated"}

@router.delete("/attendance/{attendance_id}")
async def delete_attendance(attendance_id: int, user=Depends(get_current_user)):
    import db.queries.university as q
    await q.delete_attendance(await get_pool(), attendance_id)
    return {"id": attendance_id, "status": "deleted"}


@router.get("/summary")
async def uni_summary(user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    subjects = await q.list_subjects(pool)
    exams = await q.get_upcoming_exams(pool, 30)
    restante = await q.get_restante(pool)
    avg = await q.get_general_average(pool)
    detailed = []
    for s in subjects:
        d = await q.get_subject_details(pool, s["id"])
        detailed.append(clean_dict({**s, **d}))
    return {
        "subjects": detailed,
        "upcoming_exams": [clean_dict(dict(e)) for e in exams],
        "restante": [clean_dict(dict(r)) for r in restante],
        "average": avg,
        "overview": clean_dict(await q.get_module_overview(pool)),
        "academic_work": clean_dict(await q.get_academic_work(pool)),
    }


@router.get("/overview")
async def uni_overview(user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    return clean_dict(await q.get_module_overview(pool))


@router.get("/work")
async def uni_work(user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    return clean_dict(await q.get_academic_work(pool))


@router.get("/schedule")
async def uni_schedule(week_type: str = "current", user=Depends(get_current_user)):
    """Returnează orarul activ, grupat pentru afișarea în modulul University."""
    import db.queries.schedule as q
    pool = await get_pool()
    current_week_type = await q.get_current_week_type(pool)
    rows = await q.get_full_schedule(pool)
    if week_type not in {"current", "odd", "even", "all"}:
        raise HTTPException(status_code=422, detail="week_type invalid")
    selected_week_type = current_week_type if week_type == "current" else week_type
    visible = rows if selected_week_type == "all" else [r for r in rows if r.get("week_type") in ("both", selected_week_type)]
    return {
        "week_type": selected_week_type,
        "items": [clean_dict(row) for row in sorted(visible, key=lambda r: (r.get("day_of_week", 0), r.get("start_time") or ""))],
    }


@router.post("/schedule")
async def create_schedule_entry(data: UniversityScheduleRequest, user=Depends(get_current_user)):
    import db.queries.schedule as q
    import db.queries.university as uq
    from datetime import time
    try:
        start = time.fromisoformat(data.start_time)
        end = time.fromisoformat(data.end_time)
        day = data.day_of_week
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid schedule values") from exc
    if day < 0 or day > 6 or end <= start:
        raise HTTPException(status_code=422, detail="Intervalul orar nu este valid")
    pool = await get_pool()
    subject = await uq.get_subject_by_name(pool, data.subject_name)
    if not subject:
        raise HTTPException(status_code=422, detail="Materia trebuie să existe și să fie activă")
    async with pool.acquire() as conn:
        conflict = await conn.fetchval(
            """SELECT EXISTS (SELECT 1 FROM schedule WHERE is_active = TRUE AND day_of_week = $1
               AND (week_type = $2 OR week_type = 'both' OR $2 = 'both')
               AND start_time < $4 AND end_time > $3)""",
            day, data.week_type, start, end,
        )
    if conflict:
        raise HTTPException(status_code=409, detail="Există deja o activitate în acest interval")
    entry_id = await q.add_schedule_entry(
        pool, data.subject_name, day, start, end, data.room, data.class_type,
        data.week_type, subject_id=subject["id"],
    )
    return {"id": entry_id, "status": "created"}


@router.delete("/schedule/{schedule_id}")
async def delete_schedule_entry(schedule_id: int, user=Depends(get_current_user)):
    import db.queries.schedule as q
    pool = await get_pool()
    deleted = await q.deactivate_schedule_entry(pool, schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Intrarea nu există")
    return {"status": "deleted"}


@router.put("/schedule/{schedule_id}")
async def update_schedule_entry(schedule_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.schedule as q
    from datetime import time
    try:
        start = time.fromisoformat(str(data["start_time"]))
        end = time.fromisoformat(str(data["end_time"]))
        day = int(data["day_of_week"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Datele orarului sunt invalide") from exc
    if not data.get("subject_name") or day < 0 or day > 6 or end <= start:
        raise HTTPException(status_code=422, detail="Datele orarului sunt invalide")
    pool = await get_pool()
    updated = await q.update_schedule_entry(pool, schedule_id, str(data["subject_name"]), day, start, end, data.get("room"), data.get("class_type", "curs"), data.get("week_type", "both"))
    if not updated:
        raise HTTPException(status_code=404, detail="Intrarea nu există")
    return {"status": "updated"}


@router.post("/calendar-sync")
async def sync_university_calendar(user=Depends(get_current_user)):
    """Pornește sincronizarea manuală a orarului universitar cu Calendar."""
    from core.icloud import sync_university_schedule_to_calendar
    pool = await get_pool()
    try:
        result = await sync_university_schedule_to_calendar(pool)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Sincronizarea Calendar nu este disponibilă") from exc
    return clean_dict(result if isinstance(result, dict) else {"result": result})


@router.get("/subjects")
async def list_subjects(user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    rows = await q.list_subjects(pool)
    return [clean_dict(dict(r)) for r in rows]


@router.get("/subjects/{subject_id}")
async def get_subject(subject_id: int, user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    d = await q.get_subject_details(pool, subject_id)
    return clean_dict(d) if d else {"error": "not found"}
