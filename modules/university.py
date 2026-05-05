# modules/university.py

from typing import Dict, Any, Tuple
from datetime import date
import db.queries.university as uni_queries
from bot.formatter import escape_md


async def handle_university_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, None]:

    if intent == "uni_add_subject":
        name = data.get("name", "")
        if not name:
            return "Care e numele materiei?", None

        credits = data.get("credits")
        professor = data.get("professor")
        total_classes = data.get("total_classes", 0)

        await uni_queries.add_subject(pool, name, credits, professor, total_classes)

        details = []
        if credits:
            details.append(f"{credits} credite")
        if professor:
            details.append(f"prof. {professor}")
        details_str = f" \\({escape_md(', '.join(details))}\\)" if details else ""

        return f"*{escape_md(name)}* adăugată{details_str}\\. 📚", None

    elif intent == "uni_list":
        subjects = await uni_queries.list_subjects(pool)
        if not subjects:
            return 'Nicio materie adăugată\\. Spune-mi: "adaugă materia X"\\.', None

        avg = await uni_queries.get_general_average(pool)

        lines = ["🎓 *Situație academică*\n"]

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

        return "\n".join(lines), None

    elif intent == "uni_log_attendance":
        subject_name = data.get("subject", "")
        attended = data.get("attended", True)
        class_date = data.get("date", date.today())

        if not subject_name:
            return "La ce materie?", None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return f"Materia *{escape_md(subject_name)}* nu e în listă\\.", None

        if isinstance(class_date, str):
            from datetime import datetime

            class_date = datetime.strptime(class_date, "%Y-%m-%d").date()

        await uni_queries.log_attendance(pool, subject["id"], attended, class_date)

        status = "prezent ✅" if attended else "absent ❌"
        return (
            f"*{escape_md(subject['name'])}* — {status} înregistrat\\.",
            None,
        )

    elif intent == "uni_add_grade":
        subject_name = data.get("subject", "")
        grade = data.get("grade")
        grade_type = data.get("grade_type", "exam")

        if not subject_name or grade is None:
            return "Spune-mi materia și nota.", None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return f"Materia *{escape_md(subject_name)}* nu e în listă\\.", None

        await uni_queries.add_grade(pool, subject["id"], float(grade), grade_type)

        return (
            f"Notă *{grade}* la *{escape_md(subject['name'])}* \\({escape_md(grade_type)}\\) salvată\\.",
            None,
        )

    elif intent == "uni_add_exam":
        subject_name = data.get("subject", "")
        exam_date = data.get("exam_date")
        exam_type = data.get("exam_type", "examen")
        location = data.get("location")

        if not subject_name or not exam_date:
            return "Spune-mi materia și data examenului.", None

        subject = await uni_queries.get_subject_by_name(pool, subject_name)
        if not subject:
            return f"Materia *{escape_md(subject_name)}* nu e în listă\\.", None

        if isinstance(exam_date, str):
            from datetime import datetime

            exam_date = datetime.strptime(exam_date, "%Y-%m-%d").date()

        await uni_queries.add_exam(pool, subject["id"], exam_date, exam_type, location)

        loc_str = f" la {escape_md(location)}" if location else ""
        return (
            f"Examen *{escape_md(subject['name'])}* pe *{exam_date.strftime('%d %b')}*{loc_str} adăugat\\. 📅",
            None,
        )

    elif intent == "uni_exams":
        exams = await uni_queries.get_upcoming_exams(pool, days=60)
        if not exams:
            return "Niciun examen înregistrat în următoarele 60 zile\\.", None

        lines = ["📅 *Examene upcoming*\n"]
        for e in exams:
            date_str = escape_md(e["exam_date"].strftime("%d %b"))
            subject = escape_md(e["subject_name"])
            type_str = escape_md(e["exam_type"])
            loc = f" · {escape_md(e['location'])}" if e.get("location") else ""
            lines.append(f"• *{date_str}* — {subject} \\({type_str}\\){loc}")

        return "\n".join(lines), None

    elif intent == "uni_attendance_warning":
        warnings = await uni_queries.get_attendance_warnings(pool)
        if not warnings:
            return "Prezențele sunt ok la toate materiile\\. ✅", None

        lines = ["⚠️ *Prezențe sub minim*\n"]
        for w in warnings:
            name = escape_md(w["name"])
            lines.append(
                f"• *{name}*: {w['attended']}/{w['total']} \\({int(w['pct'])}% din minimul de {w['min_attendance_pct']}%\\)"
            )

        return "\n".join(lines), None

    return "Nu am înțeles cererea legată de facultate\\.", None
