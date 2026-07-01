from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api/university", tags=["university"])


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
        detailed.append(clean_dict(d))
    return {
        "subjects": detailed,
        "upcoming_exams": [clean_dict(dict(e)) for e in exams],
        "restante": [clean_dict(dict(r)) for r in restante],
        "average": avg,
    }


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
