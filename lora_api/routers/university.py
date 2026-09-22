from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from fastapi import HTTPException

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


@router.post("/grades")
async def create_grade(data: dict, user=Depends(get_current_user)):
    import db.queries.university as q
    pool = await get_pool()
    subject_id = data.get("subject_id")
    if not subject_id or data.get("grade") is None:
        raise HTTPException(status_code=422, detail="subject_id and grade are required")
    grade_id = await q.add_grade_with_weight(pool, int(subject_id), float(data["grade"]), data.get("grade_type", "exam"), data.get("weight"), data.get("assessment_title"), data.get("assessment_date"), data.get("notes"))
    return {"id": grade_id, "status": "created"}


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
    attendance_id = await q.log_attendance(pool, int(data["subject_id"]), bool(data["attended"]), class_date, data.get("notes"))
    return {"id": attendance_id, "status": "created"}


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
