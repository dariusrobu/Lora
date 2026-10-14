import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight, GraduationCap, MapPin } from "lucide-react"
import { fetchWeek } from "../../api/queries/calendar"
import { addDays, fromLocalDate, localDate, mondayOf, shortTime } from "./date"

export default function AcademicCalendar() {
  const [view, setView] = useState<"week" | "month">("week")
  const [selectedDate, setSelectedDate] = useState(() => localDate(new Date()))
  const [week, setWeek] = useState(() => mondayOf(new Date()))
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1))

  const monthStart = mondayOf(month)
  const monthWeekCount = Math.ceil((((month.getDay() + 6) % 7) + new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()) / 7)
  const monthDates = Array.from({ length: monthWeekCount * 7 }, (_, index) => addDays(monthStart, index))
  const weekDates = Array.from({ length: 7 }, (_, index) => addDays(week, index))

  const weekQuery = useQuery({
    queryKey: ["calendar", "week", localDate(week)],
    queryFn: () => fetchWeek(week),
  })
  const monthQuery = useQuery({
    queryKey: ["calendar", "month", localDate(month)],
    queryFn: async () => (await Promise.all(Array.from({ length: monthWeekCount }, (_, index) => fetchWeek(addDays(monthStart, index * 7))))).flat(),
    enabled: view === "month",
  })
  const activeQuery = view === "month" ? monthQuery : weekQuery
  const days = activeQuery.data
  const classes = [...(days?.find((day) => day.date === selectedDate)?.schedule ?? [])]
    .sort((a, b) => a.start_time.localeCompare(b.start_time))
  const periodLabel = view === "month"
    ? month.toLocaleDateString("ro-RO", { month: "long", year: "numeric" })
    : `${week.toLocaleDateString("ro-RO", { day: "numeric", month: "long" })} – ${addDays(week, 6).toLocaleDateString("ro-RO", { day: "numeric", month: "long", year: "numeric" })}`

  function chooseDate(day: Date) {
    setSelectedDate(localDate(day))
    setWeek(mondayOf(day))
    setMonth(new Date(day.getFullYear(), day.getMonth(), 1))
  }

  function movePeriod(offset: number) {
    if (view === "week") chooseDate(addDays(week, offset * 7))
    else chooseDate(new Date(month.getFullYear(), month.getMonth() + offset, 1))
  }

  return <div className="academic-calendar">
    <section className="daily-panel daily-calendar-panel" aria-label="Calendarul facultății">
      <div className="daily-calendar-view"><span className="daily-segmented" role="group" aria-label="Vedere orar">
        <button type="button" className={view === "week" ? "selected" : ""} onClick={() => { setWeek(mondayOf(fromLocalDate(selectedDate))); setView("week") }}>Săptămână</button>
        <button type="button" className={view === "month" ? "selected" : ""} onClick={() => { const day = fromLocalDate(selectedDate); setMonth(new Date(day.getFullYear(), day.getMonth(), 1)); setView("month") }}>Lună</button>
      </span></div>
      <div className="daily-calendar-toolbar">
        <button type="button" className="daily-text-button" onClick={() => chooseDate(new Date())}>Azi</button>
        <strong>{periodLabel}</strong>
        <div><button type="button" onClick={() => movePeriod(-1)} aria-label={view === "month" ? "Luna trecută" : "Săptămâna trecută"}><ChevronLeft size={19} /></button><button type="button" onClick={() => movePeriod(1)} aria-label={view === "month" ? "Luna viitoare" : "Săptămâna viitoare"}><ChevronRight size={19} /></button></div>
      </div>
      {view === "month" && <div className="daily-month-weekdays" aria-hidden="true">{["L", "M", "M", "J", "V", "S", "D"].map((day, index) => <span key={index}>{day}</span>)}</div>}
      <div className={view === "month" ? "daily-month-grid" : "daily-week-strip"}>
        {(view === "month" ? monthDates : weekDates).map((day) => {
          const date = localDate(day)
          const selected = date === selectedDate
          const count = days?.find((item) => item.date === date)?.schedule.length ?? 0
          return <button type="button" key={date} onClick={() => chooseDate(day)} aria-label={`${day.toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" })}, ${count} ${count === 1 ? "activitate" : "activități"}`} aria-pressed={selected} className={`daily-day ${selected ? "is-selected" : ""} ${date === localDate(new Date()) ? "is-today" : ""} ${view === "month" && day.getMonth() !== month.getMonth() ? "is-outside" : ""}`}>
            <span>{day.toLocaleDateString("ro-RO", { weekday: "short" })}</span><strong>{day.getDate()}</strong><i aria-hidden="true" className={count > 0 ? "has-items" : ""} />
          </button>
        })}
      </div>
    </section>
    <section className="daily-panel daily-day-panel" aria-live="polite">
      <div className="daily-section-heading"><div><p className="daily-eyebrow">ORARUL ZILEI</p><h2>{fromLocalDate(selectedDate).toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" })}</h2></div></div>
      {activeQuery.isPending ? <p className="daily-state">Se încarcă orarul…</p>
        : activeQuery.isError ? <p className="daily-state daily-error">Orarul nu a putut fi încărcat. <button type="button" onClick={() => activeQuery.refetch()}>Reîncearcă</button></p>
          : classes.length === 0 ? <p className="daily-state">Nu ai activități la facultate în această zi.</p>
            : <div className="daily-agenda-list">{classes.map((item) => <div className="daily-agenda-item daily-class" key={item.id}>
              <span className="daily-agenda-time">{shortTime(item.start_time)}<small>{shortTime(item.end_time)}</small></span><span className="daily-agenda-line" aria-hidden="true" />
              <span className="daily-agenda-content"><strong>{item.subject_name}</strong><small>{item.class_type ? item.class_type.charAt(0).toUpperCase() + item.class_type.slice(1) : "Activitate"}{item.room ? ` · sala ${item.room}` : ""}</small></span>
              {item.room ? <MapPin size={17} aria-label="Sală" /> : <GraduationCap size={17} aria-hidden="true" />}
            </div>)}</div>}
    </section>
  </div>
}
