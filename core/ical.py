# core/ical.py

from datetime import datetime, date, time, timedelta
import pytz
from icalendar import Calendar, Event, vRecur
from core.config import TIMEZONE

def get_tz():
    return pytz.timezone(TIMEZONE)

async def generate_user_calendar(pool) -> bytes:
    """
    Generează un calendar în format iCalendar (.ics) pentru utilizator.
    Include evenimente, remindere, examene și orarul universitar.
    """
    cal = Calendar()
    cal.add('prodid', '-//Lora Assistant//lora.bot//RO')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Lora Assistant Calendar')
    cal.add('x-wr-timezone', TIMEZONE)

    tz = get_tz()

    async with pool.acquire() as conn:
        # 1. Evenimente și Remindere
        events_rows = await conn.fetch("SELECT * FROM events")
        for row in events_rows:
            e = Event()
            # UID și DTSTAMP pentru compatibilitate
            e.add('uid', f"event-{row['id']}@lora.bot")
            e.add('dtstamp', datetime.now(tz))
            
            e.add('summary', row['title'])
            if row['description']:
                e.add('description', row['description'])
            
            # Data și ora
            ev_date = row['event_date']
            ev_time = row['event_time'] or time(0, 0)
            dt_start = tz.localize(datetime.combine(ev_date, ev_time))
            e.add('dtstart', dt_start)
            
            if row['event_time']:
                # Dacă are oră, punem o durată de 1 oră implicită dacă nu e specificat altfel
                e.add('dtend', dt_start + timedelta(hours=1))
            else:
                # Allday event
                e.add('dtstart', ev_date)
                e.add('dtend', ev_date + timedelta(days=1))

            # Recurență
            if row['is_recurring'] and row['recurrence']:
                freq_map = {
                    'daily': 'DAILY',
                    'weekly': 'WEEKLY',
                    'monthly': 'MONTHLY',
                    'yearly': 'YEARLY'
                }
                freq = freq_map.get(row['recurrence'])
                if freq:
                    e.add('rrule', {'FREQ': freq})

            cal.add_component(e)

        # 2. Examene
        exams_rows = await conn.fetch("""
            SELECT e.*, s.name as subject_name 
            FROM exams e
            JOIN subjects s ON s.id = e.subject_id
        """)
        for row in exams_rows:
            e = Event()
            e.add('uid', f"exam-{row['id']}@lora.bot")
            e.add('dtstamp', datetime.now(tz))
            
            summary = f"Examen: {row['subject_name']}"
            if row['exam_type']:
                summary += f" ({row['exam_type']})"
            e.add('summary', summary)
            
            if row['notes']:
                e.add('description', row['notes'])
            if row['room']:
                e.add('location', row['room'])
            
            dt_start = tz.localize(datetime.combine(row['exam_date'], time(9, 0))) # Default 09:00
            e.add('dtstart', dt_start)
            e.add('dtend', dt_start + timedelta(hours=3)) # Default 3 ore
            cal.add_component(e)

        # 3. Orar (Schedule)
        schedule_rows = await conn.fetch("SELECT * FROM schedule WHERE is_active = TRUE")
        sem_config = await conn.fetchrow("SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1")
        
        if sem_config:
            sem_start = sem_config['semester_start']
            for row in schedule_rows:
                e = Event()
                e.add('uid', f"schedule-{row['id']}@lora.bot")
                e.add('dtstamp', datetime.now(tz))
                
                e.add('summary', f"{row['subject_name']} ({row['class_type']})")
                
                desc = f"Tip: {row['class_type']}\nSăptămână: {row['week_type']}"
                e.add('description', desc)
                if row['room']:
                    e.add('location', row['room'])

                # Calculăm prima apariție
                # weekday(): 0=Luni, 6=Duminică. In DB schedule.day_of_week is also 0=Luni
                target_dow = row['day_of_week']
                
                # Găsim prima zi din semestru care corespunde target_dow
                days_ahead = target_dow - sem_start.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                
                first_occurrence = sem_start + timedelta(days=days_ahead)
                
                # Ajustăm pentru paritate dacă e cazul
                # Săptămâna 1 este impar (week_number = 1)
                # Dacă row['week_type'] == 'par', trebuie să înceapă în săptămâna 2
                if row['week_type'] == 'par':
                    first_occurrence += timedelta(weeks=1)
                
                dt_start = tz.localize(datetime.combine(first_occurrence, row['start_time']))
                dt_end = tz.localize(datetime.combine(first_occurrence, row['end_time']))
                
                e.add('dtstart', dt_start)
                e.add('dtend', dt_end)

                # Recurență
                rrule = {'FREQ': 'WEEKLY'}
                if row['week_type'] in ('par', 'impar'):
                    rrule['INTERVAL'] = 2
                
                # Limităm recurența la 14 săptămâni (un semestru tipic)
                rrule['COUNT'] = 14 if row['week_type'] == 'both' else 7
                
                e.add('rrule', rrule)
                cal.add_component(e)

    return cal.to_ical()
