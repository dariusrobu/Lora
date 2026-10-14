import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { Bell, CalendarDays, ChevronLeft, ChevronRight, Clock3, GraduationCap, MapPin, Plus, X } from "lucide-react"
import { createEvent, fetchWeek } from "../../api/queries/calendar"
import type { CalendarDay } from "../../types"
import { addDays, localDate, mondayOf, shortTime } from "./date"
import { LoginRequired } from "./LoginRequired"
import { isUnauthorized } from "./isUnauthorized"

export default function DailyCalendar() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [week, setWeek] = useState(() => mondayOf(new Date()))
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1))
  const [view, setView] = useState<"week" | "month">("week")
  const [selectedDate, setSelectedDate] = useState(() => localDate(new Date()))
  const [formOpen, setFormOpen] = useState(false)
  const [title, setTitle] = useState("")
  const [time, setTime] = useState("")
  const [kind, setKind] = useState<"event" | "reminder">("event")
  const [description, setDescription] = useState("")
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ["calendar", "week", localDate(week)], queryFn: () => fetchWeek(week) })
  const monthStart = mondayOf(month)
  const monthWeekCount = Math.ceil(((month.getDay() + 6) % 7 + new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()) / 7)
  const monthDates = Array.from({ length: monthWeekCount * 7 }, (_, index) => addDays(monthStart, index))
  const monthQuery = useQuery({
    queryKey: ["calendar", "month", localDate(month)],
    queryFn: async () => (await Promise.all(Array.from({ length: monthWeekCount }, (_, index) => fetchWeek(addDays(monthStart, index * 7))))).flat(),
    enabled: view === "month",
  })
  const action = searchParams.get("action")
  const visibleForm = formOpen || action === "event" || action === "reminder" || action === "add"
  const selectedKind = action === "reminder" ? "reminder" : action === "event" || action === "add" ? "event" : kind
  const create = useMutation({
    mutationFn: createEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] })
      setTitle("")
      setTime("")
      setDescription("")
      setFormOpen(false)
      setSearchParams({}, { replace: true })
    },
  })

  const dates = Array.from({ length: 7 }, (_, index) => addDays(week, index))
  const days = view === "month" ? monthQuery.data : query.data
  const activeQuery = view === "month" ? monthQuery : query
  const selected: CalendarDay | undefined = days?.find((day) => day.date === selectedDate)
  const periodLabel = view === "month" ? month.toLocaleDateString("ro-RO", { month: "long", year: "numeric" }) : `${week.toLocaleDateString("ro-RO", { day: "numeric", month: "long" })} – ${addDays(week, 6).toLocaleDateString("ro-RO", { day: "numeric", month: "long", year: "numeric" })}`
  const chooseWeek = (offset: number) => { const next = addDays(week, offset * 7); setWeek(next); setSelectedDate(localDate(next)) }
  const chooseMonth = (offset: number) => { const next = new Date(month.getFullYear(), month.getMonth() + offset, 1); setMonth(next); setSelectedDate(localDate(next)); setWeek(mondayOf(next)) }
  const resetToday = () => { const now = new Date(); setWeek(mondayOf(now)); setMonth(new Date(now.getFullYear(), now.getMonth(), 1)); setSelectedDate(localDate(now)) }
  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!title.trim() || !selectedDate) return
    create.mutate({ title: title.trim(), date: selectedDate, time: time || undefined, description: description.trim() || undefined, type: selectedKind })
  }
  if (isUnauthorized(query.error, monthQuery.error, create.error)) return <LoginRequired />

  return <div className="daily-page">
    <div className="daily-page-heading"><div><p className="daily-eyebrow">PLANIFICARE</p><h1>Calendar</h1><p className="daily-subtitle">Evenimente, remindere și programul academic, împreună.</p></div><button type="button" className="daily-primary-button" onClick={() => { setFormOpen(!visibleForm); setSearchParams({}, { replace: true }) }}><Plus size={17} /> Adaugă</button></div>
    <div className="daily-panel daily-calendar-panel">
      <div className="daily-calendar-view"><span className="daily-segmented" role="group" aria-label="Vedere calendar"><button type="button" className={view === "week" ? "selected" : ""} onClick={() => { setWeek(mondayOf(new Date(`${selectedDate}T12:00:00`))); setView("week") }}>Săptămână</button><button type="button" className={view === "month" ? "selected" : ""} onClick={() => { const selected = new Date(`${selectedDate}T12:00:00`); setMonth(new Date(selected.getFullYear(), selected.getMonth(), 1)); setView("month") }}>Lună</button></span></div>
      <div className="daily-calendar-toolbar"><button type="button" className="daily-text-button" onClick={resetToday}>Azi</button><strong>{periodLabel}</strong><div><button type="button" onClick={() => view === "month" ? chooseMonth(-1) : chooseWeek(-1)} aria-label={view === "month" ? "Luna trecută" : "Săptămâna trecută"}><ChevronLeft size={19} /></button><button type="button" onClick={() => view === "month" ? chooseMonth(1) : chooseWeek(1)} aria-label={view === "month" ? "Luna viitoare" : "Săptămâna viitoare"}><ChevronRight size={19} /></button></div></div>
      {view === "month" && <div className="daily-month-weekdays" aria-hidden="true">{["L", "M", "M", "J", "V", "S", "D"].map((day, index) => <span key={index}>{day}</span>)}</div>}
      <div className={view === "month" ? "daily-month-grid" : "daily-week-strip"}>{(view === "month" ? monthDates : dates).map((day) => {
        const key = localDate(day)
        const record = days?.find((item) => item.date === key)
        const active = selectedDate === key
        return <button type="button" className={`daily-day ${active ? "is-selected" : ""} ${key === localDate(new Date()) ? "is-today" : ""} ${view === "month" && day.getMonth() !== month.getMonth() ? "is-outside" : ""}`} key={key} onClick={() => { setSelectedDate(key); setWeek(mondayOf(day)); if (view === "month" && day.getMonth() !== month.getMonth()) setMonth(new Date(day.getFullYear(), day.getMonth(), 1)) }} aria-pressed={active}>
          <span>{day.toLocaleDateString("ro-RO", { weekday: "short" })}</span><strong>{day.getDate()}</strong><i aria-hidden="true" className={record && record.events.length + record.schedule.length > 0 ? "has-items" : ""} />
        </button>
      })}</div>
    </div>

    {visibleForm && <form className="daily-panel daily-inline-form" onSubmit={submit}>
      <div className="daily-section-heading"><div><p className="daily-eyebrow">ADĂUGARE RAPIDĂ</p><h2>{selectedKind === "event" ? "Eveniment nou" : "Reminder nou"}</h2></div><button type="button" onClick={() => { setFormOpen(false); setSearchParams({}, { replace: true }) }} aria-label="Închide formularul"><X size={18} /></button></div>
      <div className="daily-segmented" role="group" aria-label="Tip"><button type="button" className={selectedKind === "event" ? "selected" : ""} onClick={() => { setKind("event"); setSearchParams({}, { replace: true }); setFormOpen(true) }}>Eveniment</button><button type="button" className={selectedKind === "reminder" ? "selected" : ""} onClick={() => { setKind("reminder"); setSearchParams({}, { replace: true }); setFormOpen(true) }}>Reminder</button></div>
      <label className="daily-field"><span>Ce anume?</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={selectedKind === "event" ? "Ex. Meci de fotbal" : "Ex. Sună administratorul"} required autoFocus /></label>
      <div className="daily-form-grid"><label className="daily-field"><span>Data</span><input type="date" value={selectedDate} onChange={(event) => { const value = event.target.value; setSelectedDate(value); if (value) { const selected = new Date(`${value}T12:00:00`); setWeek(mondayOf(selected)); setMonth(new Date(selected.getFullYear(), selected.getMonth(), 1)) } }} required /></label><label className="daily-field"><span>Ora {selectedKind === "reminder" ? "" : "(opțional)"}</span><input type="time" value={time} onChange={(event) => setTime(event.target.value)} required={selectedKind === "reminder"} /></label></div>
      <label className="daily-field"><span>Detalii (opțional)</span><input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Adaugă context util" /></label>
      {selectedKind === "event" && time && <p className="daily-form-note">Notificare cu 30 de minute înainte și la ora evenimentului.</p>}
      {create.isError && <p className="daily-inline-error">Nu s-a putut salva. Verifică datele și încearcă din nou.</p>}
      <button type="submit" className="daily-primary-button daily-submit" disabled={create.isPending || !title.trim()}>{create.isPending ? "Se salvează…" : "Salvează"}</button>
    </form>}

    <div className="daily-panel daily-day-panel">
      <div className="daily-section-heading"><div><p className="daily-eyebrow">PROGRAMUL ZILEI</p><h2>{selectedDate ? new Date(`${selectedDate}T12:00:00`).toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" }) : "Alege o zi"}</h2></div></div>
      {activeQuery.isPending ? <p className="daily-state">Se încarcă programul…</p> : activeQuery.isError ? <p className="daily-state daily-error">Calendarul nu a putut fi încărcat. <button type="button" onClick={() => activeQuery.refetch()}>Reîncearcă</button></p> : !selected || selected.events.length + selected.schedule.length === 0 ? <p className="daily-state">Nu este nimic planificat în această zi.</p> : <div className="daily-agenda-list">
        {[
          ...selected.events.map((item) => ({ id: `event-${item.id}`, title: item.title, time: shortTime(item.event_time), detail: item.description, kind: item.event_type === "reminder" ? "reminder" : "event" })),
          ...selected.schedule.map((item) => ({ id: `class-${item.id}`, title: item.subject_name, time: shortTime(item.start_time), detail: [item.class_type, item.room].filter(Boolean).join(" · "), kind: "class" })),
        ].sort((a, b) => (a.time || "99:99").localeCompare(b.time || "99:99")).map((item) => <div className={`daily-agenda-item daily-${item.kind}`} key={item.id}><span className="daily-agenda-time">{item.time || "Toată ziua"}</span><span className="daily-agenda-line" aria-hidden="true" /><span className="daily-agenda-content"><strong>{item.title}</strong><small>{item.detail || (item.kind === "reminder" ? "Reminder" : item.kind === "class" ? "Facultate" : "Eveniment")}</small></span>{item.kind === "reminder" ? <Bell size={17} /> : item.kind === "class" ? <GraduationCap size={17} /> : <CalendarDays size={17} />}</div>)}
      </div>}
    </div>
    <div className="daily-calendar-legend"><span><i className="legend-event" /> Eveniment</span><span><i className="legend-reminder" /> Reminder</span><span><i className="legend-class" /> Facultate</span><span><Clock3 size={14} /> Ore locale</span><span><MapPin size={14} /> Săli din orar</span></div>
  </div>
}
