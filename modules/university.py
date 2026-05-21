# modules/university.py

from typing import Dict, Any, Tuple, Optional
from datetime import date
import db.queries.university as uni_queries
from bot.formatter import escape_md


async def handle_university_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, Any, Optional[int]]:

    if intent == "uni_add_subject":
        name = data.get("name", "")
        if not name:
            return "⚠️ Atenție: Specifică numele materiei.", None, None

        credits = data.get("credits")
        professor = data.get("professor")
        total_classes = data.get("total_classes", 0)

        subject_id = await uni_queries.add_subject(
            pool, name, credits, professor, total_classes
        )

        details = []
        if credits:
            details.append(f"{credits} credite")
        if professor:
            details.append(f"prof. {professor}")
        details_str = f" \\({escape_md(', '.join(details))}\\)" if details else ""

        return (
            f"✅ Materia *{escape_md(name)}* a fost adăugată cu succes{details_str}\\.",
            None,
            subject_id,
        )

    elif intent == "uni_list":
        subjects = await uni_queries.list_subjects(pool)
        if not subjects:
            return "✅ Nu ai nicio materie adăugată.", None, None

        avg = await uni_queries.get_general_average(pool)

        lines = ["🎓 *Situație Academică*", "━━━━━━━━━━━━━━━━━━━━"]

        if avg:
            lines.append(f"📊 Medie generală: *{avg}*\n")

        for s in subjects:
            name = escape_md(s["name"])
            attended = s.get("attended_count") or 0
            total_logged = s.get("total_logged") or 0
            total_seminars = s.get("total_seminars") or 0

            # Medie materie
            avg_val = s.get("avg_grade")
            avg_str = f"*{avg_val}*" if avg_val else "—"

            # Format requested: Note: — (sau nota)
            # Prezențe: 3/7 (sau —)
            if total_seminars > 0:
                # Folosește totalul real din semestru
                pct = int(attended / total_seminars * 100) if total_seminars > 0 else 0
                warn = " ⚠️" if pct < s["min_attendance_pct"] else ""
                pres_str = f"{attended}/{total_seminars} \\({pct}%\\){warn}"
            elif total_logged > 0:
                # Fallback la ce e logat
                pct = int(attended / total_logged * 100)
                warn = " ⚠️" if pct < s["min_attendance_pct"] else ""
                pres_str = f"{attended}/{total_logged} \\({pct}%\\){warn}"
            else:
                pres_str = "—"

            lines.append(f"*{name}*\nNote: {avg_str}\nPrezențe: {escape_md(pres_str)}")

        return "\n".join(lines), None, None

    elif intent == "uni_log_attendance":
        subject_name = data.get("subject", "")
        attended = data.get("attended", True)
        class_date = data.get("date", date.today())
        notes = data.get("notes") or data.get("reflection")

        if not subject_name:
            return "⚠️ Atenție: Specifică materia.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită\\.",
                None,
                None,
            )

        if isinstance(class_date, str):
            from datetime import datetime

            class_date = datetime.strptime(class_date, "%Y-%m-%d").date()

        att_id = await uni_queries.log_attendance(
            pool, subject["id"], attended, class_date, notes=notes
        )

        status = "prezent ✅" if attended else "absent ❌"
        return (
            f"✅ *{escape_md(subject['name'])}*: {status} înregistrat\\.",
            None,
            att_id,
        )

    elif intent == "uni_add_grade":
        subject_name = data.get("subject", "")
        grade = data.get("grade")
        grade_type = data.get("grade_type", "exam")

        if not subject_name or grade is None:
            return "⚠️ Atenție: Specifică materia și nota.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită\\.",
                None,
                None,
            )

        grade_id = await uni_queries.add_grade(
            pool, subject["id"], float(grade), grade_type
        )

        return (
            f"✅ Notă *{grade}* adăugată la *{escape_md(subject['name'])}* \\({escape_md(grade_type)}\\)\\.",
            None,
            grade_id,
        )

    elif intent == "uni_add_exam":
        subject_name = data.get("subject", "")
        exam_date = data.get("exam_date")
        exam_type = data.get("exam_type", "examen")
        room = data.get("room") or data.get("location")

        if not subject_name or not exam_date:
            return "⚠️ Atenție: Specifică materia și data examenului.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită\\.",
                None,
                None,
            )

        if isinstance(exam_date, str):
            from datetime import datetime

            exam_date = datetime.strptime(exam_date, "%Y-%m-%d").date()

        exam_id = await uni_queries.add_exam(
            pool, subject["id"], exam_date, exam_type, room
        )

        loc_str = f" la {escape_md(room)}" if room else ""
        return (
            f"✅ Examen *{escape_md(subject['name'])}* adăugat pentru *{exam_date.strftime('%d %b')}*{loc_str}\\.",
            None,
            exam_id,
        )

    elif intent == "uni_exams":
        exams = await uni_queries.get_upcoming_exams(pool, days=60)
        if not exams:
            return "✅ Niciun examen în următoarele 60 zile\\.", None, None

        lines = ["📅 *Următoarele Examene*", "━━━━━━━━━━━━━━━━━━━━"]
        for e in exams:
            date_str = escape_md(e["exam_date"].strftime("%d %b"))
            subject = escape_md(e["subject_name"])
            type_str = escape_md(e["exam_type"])
            loc = f" · {escape_md(e['room'])}" if e.get("room") else ""
            lines.append(f"• *{date_str}* — {subject} \\({type_str}\\){loc}")

        return "\n".join(lines), None, None

    elif intent == "uni_restante":
        restante = await uni_queries.get_restante(pool)
        if not restante:
            return "✅ Nu ai nicio restanță marcată\\.", None, None

        lines = ["📚 *Situație Restanțe*", "━━━━━━━━━━━━━━━━━━━━"]
        for r in restante:
            date_str = escape_md(r["exam_date"].strftime("%d %b"))
            subject = escape_md(r["subject_name"])
            loc = f" · {escape_md(r['room'])}" if r.get("room") else ""

            # Calcul zile rămase
            days_left = (r["exam_date"] - date.today()).days
            if days_left > 0:
                timer = f" \\(peste {days_left} zile\\)"
            elif days_left == 0:
                timer = " \\(astăzi\\!\\)"
            else:
                timer = f" \\({abs(days_left)} zile trecute\\)"

            lines.append(f"• *{date_str}* — {subject}{loc}{timer}")

        return "\n".join(lines), None, None

    elif intent == "uni_attendance_warning":
        warnings = await uni_queries.get_attendance_warnings(pool)
        if not warnings:
            return "✅ Prezențele sunt în regulă la toate materiile\\.", None, None

        lines = ["⚠️ *Situație Prezențe (Risc)*", "━━━━━━━━━━━━━━━━━━━━"]
        for w in warnings:
            name = escape_md(w["name"])
            lines.append(
                f"• *{name}*: {w['attended']}/{w['total']} \\({int(w['pct'])}% din minimul de {w['min_attendance_pct']}%\\)"
            )

        return "\n".join(lines), None, None

    elif intent == "uni_update_subject":
        subject_name = data.get("subject")
        if not subject_name:
            return "⚠️ Atenție: Specifică materia de modificat.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită.",
                None,
                None,
            )

        update_data = {}
        if "new_name" in data:
            update_data["name"] = data["new_name"]
        if "credits" in data:
            update_data["credits"] = data["credits"]
        if "professor" in data:
            update_data["professor"] = data["professor"]
        if "min_attendance_pct" in data:
            update_data["min_attendance_pct"] = data["min_attendance_pct"]

        if not update_data:
            return "⚠️ Atenție: Nicio modificare specificată.", None, None

        await uni_queries.update_subject(pool, subject["id"], **update_data)
        return (
            f"✏️ Materia *{escape_md(subject['name'])}* a fost actualizată.",
            None,
            None,
        )

    elif intent == "uni_delete_subject":
        subject_name = data.get("subject")
        if not subject_name:
            return "⚠️ Atenție: Specifică materia de șters.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită.",
                None,
                None,
            )

        await uni_queries.delete_subject(pool, subject["id"])
        return f"🗑️ Materia *{escape_md(subject['name'])}* a fost ștearsă.", None, None

    elif intent == "uni_update_grade":
        subject_name = data.get("subject")
        old_grade = data.get("old_grade") or data.get("grade")
        if not subject_name or old_grade is None:
            return (
                "⚠️ Atenție: Specifică materia și nota pe care vrei să o modifici.",
                None,
                None,
            )

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită.",
                None,
                None,
            )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM grades WHERE subject_id = $1 AND grade = $2 ORDER BY graded_at DESC LIMIT 1",
                subject["id"],
                float(old_grade),
            )
            if not row:
                return (
                    f"❌ Eroare: Nu am găsit nota {old_grade} la {escape_md(subject['name'])}.",
                    None,
                    None,
                )

            update_data = {}
            if "new_grade" in data:
                update_data["grade"] = float(data["new_grade"])
            if "new_type" in data or "grade_type" in data:
                update_data["grade_type"] = data.get("new_type") or data.get(
                    "grade_type"
                )

            if not update_data:
                return (
                    "⚠️ Atenție: Specifică ce vrei să modifici la această notă.",
                    None,
                    None,
                )

            await uni_queries.update_grade(pool, row["id"], **update_data)

        return (
            f"✏️ Nota de la *{escape_md(subject['name'])}* a fost actualizată.",
            None,
            None,
        )

    elif intent == "uni_update_exam":
        subject_name = data.get("subject")
        if not subject_name:
            return "⚠️ Atenție: Specifică materia.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită.",
                None,
                None,
            )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM exams WHERE subject_id = $1 ORDER BY exam_date ASC LIMIT 1",
                subject["id"],
            )
            if not row:
                return (
                    f"❌ Eroare: Nu am găsit niciun examen la {escape_md(subject['name'])}.",
                    None,
                    None,
                )

            update_data = {}
            if "new_date" in data or "exam_date" in data:
                d = data.get("new_date") or data.get("exam_date")
                if isinstance(d, str):
                    from datetime import datetime

                    d = datetime.strptime(d, "%Y-%m-%d").date()
                update_data["exam_date"] = d
            if "new_type" in data or "exam_type" in data:
                update_data["exam_type"] = data.get("new_type") or data.get("exam_type")
            if "new_room" in data or "room" in data or "location" in data:
                update_data["room"] = (
                    data.get("new_room") or data.get("room") or data.get("location")
                )

            if not update_data:
                return (
                    "⚠️ Atenție: Nicio modificare specificată pentru examen.",
                    None,
                    None,
                )

            await uni_queries.update_exam(pool, row["id"], **update_data)

        return (
            f"✏️ Examenul de la *{escape_md(subject['name'])}* a fost actualizat.",
            None,
            None,
        )

    elif intent == "uni_delete_grade":
        subject_name = data.get("subject")
        grade_val = data.get("grade")
        if not subject_name or grade_val is None:
            return "⚠️ Atenție: Specifică materia și nota de șters.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită.",
                None,
                None,
            )

        # Găsește nota în DB
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM grades WHERE subject_id = $1 AND grade = $2 ORDER BY graded_at DESC LIMIT 1",
                subject["id"],
                float(grade_val),
            )
            if not row:
                return (
                    f"❌ Eroare: Nu am găsit nota {grade_val} la {escape_md(subject['name'])}.",
                    None,
                    None,
                )
            await uni_queries.delete_grade(pool, row["id"])

        return (
            f"🗑️ Nota {grade_val} de la *{escape_md(subject['name'])}* a fost ștearsă.",
            None,
            None,
        )

    elif intent == "uni_delete_exam":
        subject_name = data.get("subject")
        if not subject_name:
            return "⚠️ Atenție: Specifică materia.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită.",
                None,
                None,
            )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM exams WHERE subject_id = $1 ORDER BY exam_date ASC LIMIT 1",
                subject["id"],
            )
            if not row:
                return (
                    f"❌ Eroare: Nu am găsit niciun examen la {escape_md(subject['name'])}.",
                    None,
                    None,
                )
            await uni_queries.delete_exam(pool, row["id"])

        return (
            f"🗑️ Examenul de la *{escape_md(subject['name'])}* a fost șters.",
            None,
            None,
        )

    elif intent == "uni_delete_attendance":
        subject_name = data.get("subject")
        if not subject_name:
            return "⚠️ Atenție: Specifică materia.", None, None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return (
                f"❌ Eroare: Materia *{escape_md(subject_name)}* nu a fost găsită.",
                None,
                None,
            )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM attendances WHERE subject_id = $1 ORDER BY class_date DESC LIMIT 1",
                subject["id"],
            )
            if not row:
                return (
                    f"❌ Eroare: Nu am găsit nicio prezență la {escape_md(subject['name'])}.",
                    None,
                    None,
                )
            await uni_queries.delete_attendance(pool, row["id"])

        return (
            f"🗑️ Ultima prezență de la *{escape_md(subject['name'])}* a fost ștearsă.",
            None,
            None,
        )

    return "Nu am înțeles cererea legată de facultate\\.", None, None


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    if not item_id:
        return False, "Nu s-a găsit ID-ul entității de anulat."

    try:
        if intent == "uni_add_subject":
            await uni_queries.delete_subject(pool, item_id)
            return True, "Adăugarea materiei a fost anulată."
        elif intent == "uni_log_attendance":
            await uni_queries.delete_attendance(pool, item_id)
            return True, "Logarea prezenței a fost anulată."
        elif intent == "uni_add_grade":
            await uni_queries.delete_grade(pool, item_id)
            return True, "Adăugarea notei a fost anulată."
        elif intent == "uni_add_exam":
            await uni_queries.delete_exam(pool, item_id)
            return True, "Adăugarea examenului a fost anulată."

        return False, f"Anularea nu este implementată pentru intentul '{intent}'."
    except Exception as e:
        return False, f"Eroare la anulare: {str(e)}"
