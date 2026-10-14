"""Import the real year-3 schedule and seed one absence per subject."""
from datetime import date, time
import asyncio
from db.connection import get_pool, close_pool

SUBJECTS = {
    "Macroeconomie aprofundată": ("Pop Silaghi / Tomoloagă", 5),
    "Bazele econometriei": ("Todea", 4),
    "Analiză financiară": ("Pop", 5),
    "Politici comerciale": ("Rovinariu", 4),
    "Marketing în comerț": ("Dabija / Sabo", 4),
    "Jurnalism economic": ("Bodea / Bucur", 4),
    "Politici de marketing": ("Romonți", 4),
}

SCHEDULE = [
    ("Macroeconomie aprofundată", 0, "08:30", "10:00", "307", "curs", "both"),
    ("Macroeconomie aprofundată", 0, "10:15", "11:45", "307", "seminar", "both"),
    ("Bazele econometriei", 0, "13:45", "15:15", "1", "curs", "both"),
    ("Analiză financiară", 0, "15:30", "17:00", "1", "curs", "both"),
    ("Politici comerciale", 1, "08:30", "10:00", "301", "curs", "both"),
    ("Analiză financiară", 1, "10:15", "11:45", "235", "seminar", "odd"),
    ("Politici comerciale", 1, "12:00", "13:30", "301", "seminar", "both"),
    ("Marketing în comerț", 2, "08:30", "10:00", "1", "curs", "both"),
    ("Jurnalism economic", 2, "10:15", "11:45", "234", "curs", "both"),
    ("Politici de marketing", 2, "13:45", "15:15", "1", "curs", "both"),
    ("Jurnalism economic", 2, "15:30", "17:00", "422", "seminar", "both"),
    ("Bazele econometriei", 3, "08:30", "10:00", "307", "seminar", "both"),
    ("Marketing în comerț", 3, "10:15", "11:45", "307", "seminar", "odd"),
]

ABSENCE_DATES = {0: date(2026, 9, 28), 1: date(2026, 9, 29), 2: date(2026, 9, 30), 3: date(2026, 10, 1)}


async def main() -> None:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                ids = {}
                for name, (professor, credits) in SUBJECTS.items():
                    subject_id = await conn.fetchval(
                        """INSERT INTO subjects (name, professor, credits, is_active)
                           VALUES ($1, $2, $3, TRUE)
                           ON CONFLICT (name) DO UPDATE SET professor = EXCLUDED.professor, credits = EXCLUDED.credits, is_active = TRUE
                           RETURNING id""", name, professor, credits
                    )
                    ids[name] = subject_id
                for name, day, start, end, room, class_type, week_type in SCHEDULE:
                    schedule_id = await conn.fetchval(
                        """INSERT INTO schedule (subject_id, subject_name, day_of_week, start_time, end_time, room, class_type, week_type)
                           SELECT $1, $2, $3, $4::time, $5::time, $6, $7, $8
                           WHERE NOT EXISTS (SELECT 1 FROM schedule WHERE subject_id = $1 AND day_of_week = $3 AND start_time = $4::time AND class_type = $7 AND is_active = TRUE)
                           RETURNING id""", ids[name], name, day, time.fromisoformat(start), time.fromisoformat(end), room, class_type, week_type
                    )
                    if schedule_id:
                        await conn.execute(
                            """INSERT INTO attendances (schedule_id, subject_id, class_date, attended, notes)
                               VALUES ($1, $2, $3, FALSE, 'Absență inițială importată din orar')
                               ON CONFLICT (schedule_id, class_date) DO NOTHING""",
                            schedule_id, ids[name], ABSENCE_DATES[day],
                        )
                await conn.execute("""DELETE FROM attendances a USING attendances b
                    WHERE a.notes = 'Absență inițială importată din orar'
                      AND b.notes = 'Absență inițială importată din orar'
                      AND a.subject_id = b.subject_id AND a.id > b.id""")
        print({"subjects": len(ids), "schedule_entries": len(SCHEDULE), "note": "SI mapped to odd; adjust when official parity is confirmed"})
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
