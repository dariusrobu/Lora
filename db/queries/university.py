# db/queries/university.py


async def add_subject(pool, name, credits=None, professor=None, total_classes=0) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO subjects (name, credits, professor, total_classes)
            VALUES ($1, $2, $3, $4) RETURNING id
        """,
            name,
            credits,
            professor,
            total_classes,
        )


async def list_subjects(pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                s.id, s.name, s.credits, s.professor, s.min_attendance_pct,
                (SELECT ROUND(AVG(grade), 2) FROM grades WHERE subject_id = s.id) as avg_grade,
                (SELECT ROUND(SUM(grade * weight) / NULLIF(SUM(weight), 0), 2) FROM grades WHERE subject_id = s.id AND weight IS NOT NULL) as weighted_avg_grade,
                (SELECT JSON_AGG(JSON_BUILD_OBJECT('grade', grade, 'type', grade_type, 'date', graded_at)) 
                 FROM grades WHERE subject_id = s.id) as grades,
                (SELECT COUNT(*) FROM attendances WHERE subject_id = s.id AND attended = TRUE) as attended_count,
                (SELECT COUNT(*) FROM attendances WHERE subject_id = s.id) as total_logged
                ,(SELECT COUNT(*) FROM exams WHERE subject_id = s.id AND exam_date >= CURRENT_DATE) as upcoming_exam_count
                ,(SELECT COUNT(*) FROM tasks WHERE university_subject_id = s.id AND deleted_at IS NULL AND status != 'done') as open_task_count
                ,(SELECT COUNT(*) FROM projects WHERE university_subject_id = s.id AND deleted_at IS NULL) as project_count
            FROM subjects s
            WHERE s.is_active = TRUE
            ORDER BY s.name
        """)
        return [dict(r) for r in rows]


async def get_module_overview(pool) -> dict:
    """Return one compact academic overview for the dashboard and agent."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
              (SELECT COUNT(*) FROM subjects WHERE is_active = TRUE) AS subjects_count,
              (SELECT COUNT(*) FROM tasks WHERE university_subject_id IS NOT NULL AND status != 'done' AND deleted_at IS NULL) AS open_tasks,
              (SELECT COUNT(*) FROM projects WHERE university_subject_id IS NOT NULL AND deleted_at IS NULL) AS projects_count,
              (SELECT COUNT(*) FROM exams WHERE exam_date >= CURRENT_DATE) AS exams_count,
              (SELECT ROUND(SUM(g.grade * g.weight) / NULLIF(SUM(g.weight), 0), 2)
                 FROM grades g WHERE g.weight IS NOT NULL) AS weighted_average,
              (SELECT COUNT(*) FILTER (WHERE attended) FROM attendances) AS attended_count,
              (SELECT COUNT(*) FROM attendances) AS attendance_total
        """)
    result = dict(row) if row else {}
    total = result.get("attendance_total") or 0
    result["attendance_pct"] = round((result.get("attended_count") or 0) * 100 / total, 1) if total else None
    return result


async def get_academic_work(pool) -> dict:
    async with pool.acquire() as conn:
        tasks = await conn.fetch("""SELECT t.id, t.title, t.status, t.priority, t.due_date, s.name AS subject_name
            FROM tasks t JOIN subjects s ON s.id = t.university_subject_id
            WHERE t.deleted_at IS NULL AND t.status != 'done' ORDER BY t.due_date NULLS LAST, t.priority""")
        projects = await conn.fetch("""SELECT p.id, p.name, p.status, p.progress, p.deadline, s.name AS subject_name
            FROM projects p JOIN subjects s ON s.id = p.university_subject_id
            WHERE p.deleted_at IS NULL ORDER BY p.deadline NULLS LAST""")
    return {"tasks": [dict(row) for row in tasks], "projects": [dict(row) for row in projects]}


async def check_subject_has_seminar(pool, subject_name: str) -> bool:
    """Verifică dacă o materie are seminare în orar."""
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM schedule 
                WHERE LOWER(subject_name) = LOWER($1) 
                  AND class_type = 'seminar'
            )
        """,
            subject_name,
        )
        return exists


async def get_subject_by_name(pool, name) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM subjects
            WHERE LOWER(name) LIKE LOWER($1) AND is_active = TRUE
            ORDER BY created_at DESC LIMIT 1
        """,
            f"%{name}%",
        )
        return dict(row) if row else None


async def get_subject_by_id(pool, subject_id: int) -> dict | None:
    """Returnează o materie după ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM subjects WHERE id = $1", subject_id)
        return dict(row) if row else None


async def log_attendance(pool, subject_id, attended, class_date, notes=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO attendances (subject_id, attended, class_date, notes)
            VALUES ($1, $2, $3, $4) RETURNING id
        """,
            subject_id,
            attended,
            class_date,
            notes,
        )


async def add_grade(pool, subject_id, grade, grade_type="exam", notes=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO grades (subject_id, grade, grade_type, notes)
            VALUES ($1, $2, $3, $4) RETURNING id
        """,
            subject_id,
            grade,
            grade_type,
            notes,
        )


async def add_grade_with_weight(pool, subject_id, grade, grade_type="exam", weight=None, assessment_title=None, assessment_date=None, notes=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """INSERT INTO grades (subject_id, grade, grade_type, weight, assessment_title, assessment_date, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
            subject_id, grade, grade_type, weight, assessment_title, assessment_date, notes,
        )


async def add_exam(
    pool, subject_id, exam_date, exam_type="examen", room=None, notes=None
) -> int:
    async with pool.acquire() as conn:
        subject_name = await conn.fetchval("SELECT name FROM subjects WHERE id = $1", subject_id)
        return await conn.fetchval(
            """
            INSERT INTO exams (subject_id, subject_name, exam_date, exam_type, room, notes)
            VALUES ($1, $6, $2, $3, $4, $5) RETURNING id
        """,
            subject_id,
            exam_date,
            exam_type,
            room,
            notes,
            subject_name,
        )


async def get_subject_details(pool, subject_id) -> dict:
    async with pool.acquire() as conn:
        grades = await conn.fetch(
            """
            SELECT grade, grade_type, graded_at FROM grades
            WHERE subject_id = $1 ORDER BY graded_at DESC
        """,
            subject_id,
        )

        attendance = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) FILTER (WHERE attended = TRUE) as attended,
                COUNT(*) as total
            FROM attendances WHERE subject_id = $1
        """,
            subject_id,
        )

        exams = await conn.fetch(
            """
            SELECT exam_date, exam_type, room FROM exams
            WHERE subject_id = $1 AND exam_date >= CURRENT_DATE
            ORDER BY exam_date ASC
        """,
            subject_id,
        )

        return {
            "grades": [dict(g) for g in grades],
            "attendance": dict(attendance) if attendance else {},
            "upcoming_exams": [dict(e) for e in exams],
        }


async def get_general_average(pool) -> float | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT ROUND(AVG(sub_avg), 2) as general_avg
            FROM (
                SELECT subject_id, AVG(grade) as sub_avg
                FROM grades
                GROUP BY subject_id
            ) sub
        """)
        return float(row["general_avg"]) if row and row["general_avg"] else None


async def get_upcoming_exams(pool, days=30) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT e.*, s.name as subject_name
            FROM exams e
            JOIN subjects s ON s.id = e.subject_id
            WHERE e.exam_date BETWEEN CURRENT_DATE AND CURRENT_DATE + $1 * INTERVAL '1 day'
            ORDER BY e.exam_date ASC
        """,
            days,
        )
        return [dict(r) for r in rows]


async def get_attendance_warnings(pool) -> list:
    """Returnează materiile unde prezența e sub pragul minim."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.name, s.min_attendance_pct, s.total_seminars,
                COUNT(a.id) FILTER (WHERE a.attended = TRUE) as attended,
                COUNT(a.id) as total_logged,
                CASE WHEN s.total_seminars > 0
                    THEN ROUND(COUNT(a.id) FILTER (WHERE a.attended = TRUE) * 100.0 / s.total_seminars, 0)
                    WHEN COUNT(a.id) > 0
                    THEN ROUND(COUNT(a.id) FILTER (WHERE a.attended = TRUE) * 100.0 / COUNT(a.id), 0)
                    ELSE 0
                END as pct
            FROM subjects s
            LEFT JOIN attendances a ON a.subject_id = s.id
            WHERE s.is_active = TRUE AND s.total_seminars > 0
            GROUP BY s.id, s.name, s.min_attendance_pct, s.total_seminars
            HAVING CASE WHEN s.total_seminars > 0
                    THEN ROUND(COUNT(a.id) FILTER (WHERE a.attended = TRUE) * 100.0 / s.total_seminars, 0)
                    ELSE 0
                END < s.min_attendance_pct
        """)
        return [dict(r) for r in rows]


async def log_attendance_by_schedule(
    pool, schedule_id: int, attended: bool, notes: str = None
) -> None:
    """Loghează prezența folosind ID-ul din schedule."""
    from datetime import date

    async with pool.acquire() as conn:
        # Găsește subject_id-ul corespunzător
        row = await conn.fetchrow(
            "SELECT subject_id FROM schedule WHERE id = $1", schedule_id
        )
        if row:
            await log_attendance(
                pool, row["subject_id"], attended, date.today(), notes=notes
            )


async def update_subject(pool, subject_id: int, **kwargs) -> None:
    """Actualizează metadatele unei materii."""
    if not kwargs:
        return

    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=2):
        fields.append(f"{key} = ${i}")
        values.append(value)

    query = f"UPDATE subjects SET {', '.join(fields)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, subject_id, *values)


async def delete_subject(pool, subject_id: int) -> None:
    """Șterge o materie (soft delete) și dezactivează orele din orar asociate."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Soft delete subject
            await conn.execute(
                "UPDATE subjects SET is_active = FALSE WHERE id = $1", subject_id
            )
            # Deactivate schedule entries
            await conn.execute(
                "UPDATE schedule SET is_active = FALSE WHERE subject_id = $1",
                subject_id,
            )


async def get_restante(pool) -> list:
    """Returnează toate restanțele viitoare sau recente."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT e.*, s.name as subject_name
            FROM exams e
            JOIN subjects s ON s.id = e.subject_id
            WHERE e.exam_type = 'restanta'
            ORDER BY e.exam_date ASC
        """
        )
        return [dict(r) for r in rows]


# --- CRUD Extensions ---


async def delete_grade(pool, grade_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM grades WHERE id = $1", grade_id)


async def delete_exam(pool, exam_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM exams WHERE id = $1", exam_id)


async def delete_attendance(pool, attendance_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM attendances WHERE id = $1", attendance_id)


async def update_grade(pool, grade_id: int, **kwargs) -> None:
    if not kwargs:
        return
    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=2):
        fields.append(f"{key} = ${i}")
        values.append(value)
    query = f"UPDATE grades SET {', '.join(fields)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, grade_id, *values)


async def update_exam(pool, exam_id: int, **kwargs) -> None:
    if not kwargs:
        return
    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=2):
        fields.append(f"{key} = ${i}")
        values.append(value)
    query = f"UPDATE exams SET {', '.join(fields)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, exam_id, *values)


async def update_attendance(pool, attendance_id: int, **kwargs) -> None:
    if not kwargs:
        return
    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=2):
        fields.append(f"{key} = ${i}")
        values.append(value)
    query = f"UPDATE attendances SET {', '.join(fields)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, attendance_id, *values)
