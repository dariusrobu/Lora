import { useCallback, useEffect, useRef, useState } from "react"
import { CalendarDays, ChevronLeft, ChevronRight, FileText, GraduationCap, Megaphone, MessageCircle, Pencil, Plus, Trash2, X } from "lucide-react"
import { api, type Entry, type MoodleLibrary, type UniversityData, type UniversityKind, type UniversityRecord } from "./api"
import UniversityNotes from "./UniversityNotes"

type FormState = { kind: UniversityKind; id?: string; version?: number }
const sections: { kind: UniversityKind; key: keyof Pick<UniversityData, "subjects" | "schedules" | "attendance" | "grades" | "exams" | "vacations">; title: string }[] = [
  { kind: "subject", key: "subjects", title: "Materii" },
  { kind: "schedule", key: "schedules", title: "Cursuri și seminare" },
  { kind: "exam", key: "exams", title: "Examene" },
  { kind: "attendance", key: "attendance", title: "Prezențe" },
  { kind: "grade", key: "grades", title: "Note" },
  { kind: "vacation", key: "vacations", title: "Vacanțe" },
]
const weekdays = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"]
const shortDate = (value: string) => new Date(value).toLocaleDateString("ro-RO", { day: "numeric", month: "short", weekday: "short" })
const shortTime = (value: string) => new Date(value).toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit" })
const dateKey = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`
const mondayOf = (value: Date) => {
  const monday = new Date(value.getFullYear(), value.getMonth(), value.getDate())
  monday.setDate(monday.getDate() - (monday.getDay() + 6) % 7)
  return monday
}
const shiftDays = (value: Date, count: number) => new Date(value.getFullYear(), value.getMonth(), value.getDate() + count)
const inputDateTime = (value: unknown) => {
  if (!value) return ""
  const date = new Date(String(value))
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}T${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`
}

function recordLabel(kind: UniversityKind, item: UniversityRecord, subjects: UniversityRecord[]): string {
  const subject = subjects.find(row => row.id === item.subject_id)
  if (kind === "schedule") return `${weekdays[Number(item.day_of_week)]} ${String(item.start_time).slice(0, 5)} · ${item.title} ${item.class_type || ""}`
  if (kind === "attendance") return `${item.attended ? "Prezent" : "Absent"} · ${subject?.name || "Materie"} · ${item.class_date}`
  if (kind === "grade") return `${subject?.name || "Materie"} · ${item.label || "Notă"}: ${item.value ?? "—"}`
  if (kind === "exam") return `${item.title} · ${shortDate(String(item.starts_at))} ${shortTime(String(item.starts_at))}`
  if (kind === "vacation") return `${item.name || "Vacanță"} · ${item.starts_on}–${item.ends_on}`
  return String(item.name || "Materie")
}

export default function UniversityPanel() {
  const [data, setData] = useState<UniversityData | null>(null)
  const [calendar, setCalendar] = useState<Entry[]>([])
  const [moodle, setMoodle] = useState<MoodleLibrary | null>(null)
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()))
  const [selectedDay, setSelectedDay] = useState(() => dateKey(new Date()))
  const [form, setForm] = useState<FormState | null>(null)
  const [fields, setFields] = useState<Record<string, string>>({})
  const [semesterFields, setSemesterFields] = useState({ start: "", end: "" })
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const formRef = useRef<HTMLFormElement | null>(null)

  const reload = useCallback(async () => {
    setCalendar([])
    const [university, entries, library] = await Promise.all([
      api.university(), api.universityWeek(dateKey(weekStart)), api.moodle(),
    ])
    setData(university)
    setCalendar(entries)
    setMoodle(library)
    setSemesterFields({ start: university.semester?.semester_start || "", end: university.semester?.semester_end || "" })
    setError("")
  }, [weekStart])
  useEffect(() => { void reload().catch(cause => setError(cause instanceof Error ? cause.message : "Nu pot încărca facultatea.")) }, [reload])
  useEffect(() => { if (form) window.requestAnimationFrame(() => formRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })) }, [form])

  function startNew(kind: UniversityKind) {
    setForm({ kind })
    setFields(kind === "schedule" ? { day_of_week: "0", week_type: "both", class_type: "curs" } : {})
    setError("")
  }

  function startEdit(kind: UniversityKind, item: UniversityRecord) {
    const mapped: Record<string, string> = {}
    for (const [key, value] of Object.entries(item)) mapped[key] = value == null ? "" : String(value)
    if (kind === "exam") mapped.starts_at = inputDateTime(item.starts_at)
    if (kind === "grade") mapped.recorded_at = inputDateTime(item.recorded_at)
    mapped.start_time = mapped.start_time?.slice(0, 5) || ""
    mapped.end_time = mapped.end_time?.slice(0, 5) || ""
    setFields(mapped)
    setForm({ kind, id: item.id, version: item.version })
    setError("")
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!form) return
    const optional = (key: string) => fields[key]?.trim() || null
    let payload: Record<string, unknown> = {}
    if (form.kind === "subject") payload = { name: fields.name, professor: optional("professor"), credits: optional("credits") ? Number(fields.credits) : null, is_active: fields.is_active !== "false" }
    if (form.kind === "schedule") payload = { title: fields.title, subject_id: optional("subject_id"), day_of_week: Number(fields.day_of_week), start_time: fields.start_time, end_time: fields.end_time, week_type: fields.week_type || "both", class_type: optional("class_type"), room: optional("room"), valid_from: optional("valid_from"), valid_until: optional("valid_until"), is_active: fields.is_active !== "false" }
    if (form.kind === "attendance") payload = { subject_id: optional("subject_id"), schedule_rule_id: optional("schedule_rule_id"), class_date: fields.class_date, attended: fields.attended !== "false", notes: optional("notes") }
    if (form.kind === "grade") payload = { subject_id: optional("subject_id"), label: optional("label"), value: optional("value") ? Number(fields.value) : null, recorded_at: optional("recorded_at") ? new Date(fields.recorded_at).toISOString() : null }
    if (form.kind === "exam") payload = { subject_id: optional("subject_id"), title: fields.title, starts_at: new Date(fields.starts_at).toISOString(), exam_type: optional("exam_type"), room: optional("room"), notes: optional("notes") }
    if (form.kind === "vacation") payload = { name: optional("name"), starts_on: fields.starts_on, ends_on: fields.ends_on }
    setBusy(true); setError("")
    try {
      if (form.id && form.version) await api.academicEdit(form.kind, form.id, form.version, payload)
      else await api.academicCreate(form.kind, payload)
      setForm(null); setMessage("Schimbarea a fost salvată."); await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva.") }
    finally { setBusy(false) }
  }

  async function remove(kind: UniversityKind, item: UniversityRecord) {
    if (!window.confirm("Ștergi acest element?")) return
    setBusy(true); setError("")
    try { await api.academicDelete(kind, item.id, item.version); setMessage("Elementul a fost șters."); await reload() }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut șterge.") }
    finally { setBusy(false) }
  }

  async function saveSemester(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("")
    try {
      await api.academicSemester(semesterFields.start, semesterFields.end || null, data?.semester?.version || null)
      setMessage("Semestrul a fost salvat."); await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva semestrul.") }
    finally { setBusy(false) }
  }

  async function updatePost(id: string, change: { is_read?: boolean; archived?: boolean }) {
    setBusy(true); setError("")
    try { await api.updateMoodlePost(id, change); await reload() }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut modifica mesajul.") }
    finally { setBusy(false) }
  }

  const field = (key: string, label: string, type = "text", required = false) => <label key={key}>{label}<input type={type} required={required} value={fields[key] || ""} onChange={event => setFields({ ...fields, [key]: event.target.value })} /></label>
  const subjectSelect = <label>Materie<select value={fields.subject_id || ""} onChange={event => setFields({ ...fields, subject_id: event.target.value })}><option value="">Fără materie</option>{data?.subjects.filter(item => item.is_active).map(item => <option key={item.id} value={item.id}>{String(item.name)}</option>)}</select></label>

  const weekDays = Array.from({ length: 7 }, (_, index) => shiftDays(weekStart, index))
  const selectedEntries = calendar.filter(entry => dateKey(new Date(entry.starts_at)) === selectedDay)
  const selectedDate = new Date(`${selectedDay}T12:00:00`)
  function moveWeek(weeks: number) {
    setWeekStart(shiftDays(weekStart, weeks * 7))
    setSelectedDay(dateKey(shiftDays(selectedDate, weeks * 7)))
  }

  return <div className="university-panel">
    {message && <div className="toast" role="status">{message}<button onClick={() => setMessage("")} aria-label="Închide"><X size={15} /></button></div>}
    {error && <div className="error" role="alert">{error}</div>}
    <section className="glass section-card university-calendar"><div className="section-title month-title"><CalendarDays size={19} /><h2>Programul săptămânii</h2><span className="month-controls"><button aria-label="Săptămâna anterioară" onClick={() => moveWeek(-1)}><ChevronLeft size={18} /></button><button aria-label="Săptămâna următoare" onClick={() => moveWeek(1)}><ChevronRight size={18} /></button></span></div>
      <p className="university-week-label">{weekDays[0].toLocaleDateString("ro-RO", { day: "numeric", month: "short" })} – {weekDays[6].toLocaleDateString("ro-RO", { day: "numeric", month: "short", year: "numeric" })}</p>
      <div className="university-week-days" aria-label="Zilele săptămânii">{weekDays.map(day => {
        const key = dateKey(day)
        const count = calendar.filter(entry => dateKey(new Date(entry.starts_at)) === key).length
        return <button key={key} type="button" className={`university-day ${key === selectedDay ? "is-selected" : ""} ${key === dateKey(new Date()) ? "is-today" : ""}`} aria-pressed={key === selectedDay} aria-label={`${weekdays[(day.getDay() + 6) % 7]} ${day.toLocaleDateString("ro-RO", { day: "numeric", month: "long" })}, ${count} activități`} onClick={() => setSelectedDay(key)}><span>{weekdays[(day.getDay() + 6) % 7].slice(0, 3)}</span><strong>{day.getDate()}</strong><i aria-hidden="true" className={count ? "has-classes" : ""} /></button>
      })}</div>
      <h3 className="university-selected-date">{selectedDate.toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" })}</h3>
      {selectedEntries.length ? selectedEntries.map(entry => <div className="agenda-row" key={entry.id}><span className="agenda-time">{shortTime(entry.starts_at)}</span><span className="agenda-line" /><span className="agenda-text"><strong>{entry.title}</strong><small>{entry.ends_at ? `Până la ${shortTime(entry.ends_at)}` : "Examen"}{entry.notes ? ` · ${entry.notes}` : ""}</small></span></div>) : <p className="empty">Nimic programat pentru ziua aceasta.</p>}
    </section>
    <section className="glass section-card moodle-news"><div className="section-title"><Megaphone size={19} /><h2>Noutăți Moodle</h2>{moodle?.posts.some(post => !post.is_read) && <span className="moodle-count">{moodle.posts.filter(post => !post.is_read).length} noi</span>}</div>
      {moodle?.posts.length ? moodle.posts.map(post => <details key={post.id} className={`moodle-post ${post.is_read ? "" : "is-unread"}`}>
        <summary><span className="moodle-kind">{post.kind === "announcement" ? <Megaphone size={15} /> : <MessageCircle size={15} />}</span><span><strong>{post.title}</strong><small>{post.course_title} · {post.kind === "announcement" ? "Anunț" : "Forum"}</small></span></summary>
        <div className="moodle-post-body"><p>{post.body}</p><a href={post.discussion_url} target="_blank" rel="noopener noreferrer">Deschide în Moodle</a><div className="inline-actions">{!post.is_read && <button type="button" disabled={busy} onClick={() => void updatePost(post.id, { is_read: true })}>Marchează citit</button>}<button type="button" disabled={busy} onClick={() => void updatePost(post.id, { archived: true })}>Arhivează</button></div></div>
      </details>) : <p className="empty">Nu există încă mesaje extrase din Moodle.</p>}
    </section>
    <details className="glass section-card university-details moodle-files"><summary><FileText size={18} /> Materiale în iCloud Drive · {moodle?.materials.length || 0}</summary>
      <p className="helper">În aplicația Fișiere de pe iPad sau Mac: iCloud Drive → Lora → Facultate.</p>
      {moodle?.courses.map(course => <details className="moodle-course" key={course.course_url}><summary>{course.folder_name} · {course.material_count} fișiere</summary><div className="university-list">{moodle.materials.filter(file => file.course_url === course.course_url).map(file => <div className="simple-row" key={file.id}><span><strong>{file.filename}</strong><small>{file.section_title} · {file.relative_path}</small></span></div>)}</div></details>)}
      {!moodle?.courses.length && <p className="empty">Materialele vor apărea aici după sincronizarea Moodle.</p>}
    </details>
    <UniversityNotes subjects={data?.subjects || []} />
    <details className="glass section-card university-details"><summary><GraduationCap size={18} /> Date academice</summary><form className="semester-form" onSubmit={event => void saveSemester(event)}><label>Început semestru<input type="date" required value={semesterFields.start} onChange={event => setSemesterFields({ ...semesterFields, start: event.target.value })} /></label><label>Sfârșit semestru<input type="date" value={semesterFields.end} onChange={event => setSemesterFields({ ...semesterFields, end: event.target.value })} /></label><button type="submit" disabled={busy}>Salvează semestrul</button></form></details>
    {sections.map(section => <details className="glass section-card university-details" key={section.kind}><summary><span>{section.title} · {data?.[section.key].length || 0}</span></summary><div className="university-list">{data?.[section.key].map(item => <div className="simple-row" key={item.id}><span><strong>{recordLabel(section.kind, item, data.subjects)}</strong></span><span className="row-actions"><button aria-label={`Editează ${section.title}`} onClick={() => startEdit(section.kind, item)}><Pencil size={15} /></button><button aria-label={`Șterge ${section.title}`} onClick={() => void remove(section.kind, item)}><Trash2 size={15} /></button></span></div>)}</div><button className="text-action" onClick={() => startNew(section.kind)}><Plus size={15} /> Adaugă</button></details>)}
    {form && <form ref={formRef} className="glass inline-form university-form" onSubmit={event => void submit(event)}><div className="section-title"><h2>{form.id ? "Editează" : "Adaugă"} {sections.find(section => section.kind === form.kind)?.title.toLowerCase()}</h2><button className="close-form" type="button" aria-label="Închide formularul" onClick={() => setForm(null)}><X size={17} /></button></div>
      {form.kind === "subject" && <>{field("name", "Nume materie", "text", true)}{field("professor", "Profesor")}{field("credits", "Credite", "number")}</>}
      {form.kind === "schedule" && <>{subjectSelect}{field("title", "Titlu curs/seminar", "text", true)}<label>Zi<select value={fields.day_of_week || "0"} onChange={event => setFields({ ...fields, day_of_week: event.target.value })}>{weekdays.map((day, index) => <option value={index} key={day}>{day}</option>)}</select></label>{field("start_time", "De la", "time", true)}{field("end_time", "Până la", "time", true)}<label>Săptămână<select value={fields.week_type || "both"} onChange={event => setFields({ ...fields, week_type: event.target.value })}><option value="both">Toate</option><option value="odd">Impare</option><option value="even">Pare</option></select></label><label>Tip<select value={fields.class_type || "curs"} onChange={event => setFields({ ...fields, class_type: event.target.value })}><option value="curs">Curs</option><option value="seminar">Seminar</option><option value="laborator">Laborator</option></select></label>{field("room", "Sală")}{field("valid_from", "Valabil de la", "date")}{field("valid_until", "Valabil până la", "date")}</>}
      {form.kind === "attendance" && <>{subjectSelect}<label>Curs / seminar<select value={fields.schedule_rule_id || ""} onChange={event => setFields({ ...fields, schedule_rule_id: event.target.value })}><option value="">Fără asociere</option>{data?.schedules.map(item => <option value={item.id} key={item.id}>{String(item.title)} · {weekdays[Number(item.day_of_week)]}</option>)}</select></label>{field("class_date", "Data", "date", true)}<label>Prezență<select value={fields.attended || "true"} onChange={event => setFields({ ...fields, attended: event.target.value })}><option value="true">Prezent</option><option value="false">Absent</option></select></label>{field("notes", "Notă")}</>}
      {form.kind === "grade" && <>{subjectSelect}{field("label", "Tip notă")}{field("value", "Notă", "number")}{field("recorded_at", "Data", "datetime-local")}</>}
      {form.kind === "exam" && <>{subjectSelect}{field("title", "Examen", "text", true)}{field("starts_at", "Data și ora", "datetime-local", true)}{field("exam_type", "Tip")}{field("room", "Sală")}{field("notes", "Notițe")}</>}
      {form.kind === "vacation" && <>{field("name", "Nume")}{field("starts_on", "Început", "date", true)}{field("ends_on", "Sfârșit", "date", true)}</>}
      <button className="primary" type="submit" disabled={busy}>Salvează</button>
    </form>}
  </div>
}
