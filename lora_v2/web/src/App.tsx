import { useCallback, useEffect, useMemo, useState } from "react"
import { Bell, CalendarDays, Camera, Check, ChevronLeft, ChevronRight, Dumbbell, GraduationCap, HeartPulse, House, Pencil, Plus, Send, Sparkles, Trash2, Wallet, X } from "lucide-react"
import { api, telegram, type AppleConflict, type AppleConflictDetail, type CaptureStatus, type Entry, type Journal, type Project, type Proposal, type Task, type Today } from "./api"
import UniversityPanel from "./UniversityPanel"
import IncomePanel from "./IncomePanel"
import MealPanel from "./MealPanel"

type Tab = "today" | "calendar" | "projects" | "journal" | "university"
type FormKind = "task" | "project" | "event" | "reminder" | "expense" | "workout" | "meal" | "health" | null
type MealDraft = { name: string; grams: string; calories: string; protein_g: string; carbs_g: string; fat_g: string }
const blankMealItem = (): MealDraft => ({ name: "", grams: "", calories: "", protein_g: "", carbs_g: "", fat_g: "" })
type ExerciseDraft = { name: string; sets: string; reps: string; weight_kg: string }
const blankExercise = (): ExerciseDraft => ({ name: "", sets: "", reps: "", weight_kg: "" })

const tabs: { id: Tab; label: string; icon: typeof House }[] = [
  { id: "today", label: "Azi", icon: House },
  { id: "calendar", label: "Calendar", icon: CalendarDays },
  { id: "projects", label: "Proiecte", icon: Check },
  { id: "journal", label: "Jurnal", icon: Wallet },
  { id: "university", label: "Facultate", icon: GraduationCap },
]

function localDay(value: string): string { return new Date(value).toLocaleDateString("ro-RO", { day: "numeric", month: "long", weekday: "long" }) }
function hour(value: string): string { return new Date(value).toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit" }) }
function isoLocalDate(value: Date): string { return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}` }
function monthBounds(month: Date): [string, string] {
  return [new Date(month.getFullYear(), month.getMonth(), 1).toISOString(), new Date(month.getFullYear(), month.getMonth() + 1, 1).toISOString()]
}

function Empty({ children }: { children: string }) { return <p className="empty">{children}</p> }

export default function App() {
  const [tab, setTab] = useState<Tab>("today")
  const [form, setForm] = useState<FormKind>(null)
  const [captureText, setCaptureText] = useState("")
  const [captureProgress, setCaptureProgress] = useState<CaptureStatus | null>(null)
  const [status, setStatus] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [month, setMonth] = useState(() => new Date())
  const [selectedCalendarDay, setSelectedCalendarDay] = useState(() => isoLocalDate(new Date()))
  const [showFullMonth, setShowFullMonth] = useState(false)
  const [today, setToday] = useState<Today | null>(null)
  const [entries, setEntries] = useState<Entry[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [journal, setJournal] = useState<Journal | null>(null)
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [appleConflicts, setAppleConflicts] = useState<AppleConflict[]>([])
  const [openAppleConflict, setOpenAppleConflict] = useState<{ id: string; detail: AppleConflictDetail } | null>(null)
  const [fields, setFields] = useState<Record<string, string>>({})
  const [editing, setEditing] = useState<{ kind: string; id: string; version: number } | null>(null)
  const [mealItems, setMealItems] = useState<MealDraft[]>([blankMealItem()])
  const [exercises, setExercises] = useState<ExerciseDraft[]>([])

  const reload = useCallback(async () => {
    if (!telegram?.initData) return
    try {
      const [start, end] = monthBounds(month)
      const [todayData, calendarData, projectsData, tasksData, journalData, proposalData, conflictData] = await Promise.all([
        api.today(), api.calendar(start, end), api.projects(), api.tasks(), api.journal(), api.proposals(), api.appleConflicts(),
      ])
      setToday(todayData); setEntries(calendarData); setProjects(projectsData); setTasks(tasksData); setJournal(journalData); setProposals(proposalData); setAppleConflicts(conflictData)
      setError("")
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut încărca datele.") }
  }, [month])

  useEffect(() => { void reload() }, [reload])
  useEffect(() => { if (!telegram?.initData) return; const timer = window.setInterval(() => void reload(), 15000); return () => window.clearInterval(timer) }, [reload])
  useEffect(() => {
    const id = captureProgress?.id
    if (!id || (captureProgress?.receipt && ["processed", "needs_input"].includes(captureProgress.status))) return
    let active = true
    const check = async () => {
      try {
        const latest = await api.captureStatus(id)
        if (!active) return
        setCaptureProgress(current => current?.id === id ? latest : current)
        if (latest.receipt && ["processed", "needs_input"].includes(latest.status)) await reload()
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Nu am putut verifica mesajul.")
      }
    }
    void check()
    const timer = window.setInterval(() => void check(), 5000)
    return () => { active = false; window.clearInterval(timer) }
  }, [captureProgress?.id, captureProgress?.status, captureProgress?.receipt, reload])

  async function decide(id: string, accept: boolean) {
    setBusy(true); setError("")
    try {
      const result = await api.decide(id, accept)
      setStatus(accept ? result.message || "Acțiunea a fost aplicată." : "Propunerea a fost respinsă.")
      await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut procesa propunerea.") }
    finally { setBusy(false) }
  }

  async function decideFollowup(id: string, choice: "done" | "tomorrow") {
    setBusy(true); setError("")
    try {
      const result = await api.decideFollowup(id, choice)
      setStatus(result.message)
      await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut procesa răspunsul.") }
    finally { setBusy(false) }
  }

  async function inspectAppleConflict(id: string) {
    setBusy(true); setError("")
    try { setOpenAppleConflict({ id, detail: await api.appleConflictDetail(id) }) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut compara versiunile.") }
    finally { setBusy(false) }
  }

  async function resolveApple(id: string, choice: "keep_local" | "use_apple") {
    setBusy(true); setError("")
    try {
      const result = await api.resolveAppleConflict(id, choice)
      setStatus(result.message); setOpenAppleConflict(null); await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut rezolva conflictul.") }
    finally { setBusy(false) }
  }

  async function act(type: string, data: Record<string, unknown>) {
    setBusy(true); setError("")
    try {
      const result = await api.action(type, data)
      setStatus(result.message)
      if (result.status === "saved") { setForm(null); setFields({}); await reload() }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva.") }
    finally { setBusy(false) }
  }

  async function openEdit(kind: string, id: string) {
    setBusy(true); setError("")
    try {
      const item = await api.entity(kind, id)
      const at = String(item.starts_at || item.due_at || item.spent_at || item.eaten_at || item.started_at || "")
      const localAt = at ? new Date(at) : null
      const inputAt = localAt ? `${isoLocalDate(localAt)}T${String(localAt.getHours()).padStart(2, "0")}:${String(localAt.getMinutes()).padStart(2, "0")}` : ""
      setFields({
        name: String(item.name || ""), title: String(item.title || item.activity || item.description || ""),
        project: String(item.project_id || ""), at: inputAt,
        amount: String(item.amount || ""), category: String(item.category || ""),
        merchant: String(item.merchant || ""), minutes: String(item.duration_minutes || ""),
        projectStatus: String(item.status || "active"),
        alerts: JSON.stringify(item.alert_offsets_minutes || []),
        followup: item.followup_at ? "yes" : "no",
        healthDate: String(item.log_date || ""),
        sleep_hours: String(item.sleep_hours ?? ""), sleep_quality: String(item.sleep_quality || ""),
        water_ml: String(item.water_ml ?? ""), weight_kg: String(item.weight_kg ?? ""),
        cigarettes: String(item.cigarettes ?? ""), notes: String(item.notes || ""),
      })
      if (kind === "meal" && Array.isArray(item.items)) setMealItems(item.items.map(raw => {
        const food = raw as Record<string, unknown>
        return { name: String(food.name || ""), grams: String(food.grams || ""), calories: String(food.calories || ""), protein_g: String(food.protein_g || ""), carbs_g: String(food.carbs_g || ""), fat_g: String(food.fat_g || "") }
      }))
      if (kind === "workout" && Array.isArray(item.exercises)) setExercises(item.exercises.map(raw => {
        const exercise = raw as Record<string, unknown>
        return { name: String(exercise.name || ""), sets: String(exercise.sets || ""), reps: String(exercise.reps || ""), weight_kg: String(exercise.weight_kg || "") }
      }))
      setEditing({ kind, id, version: Number(item.version) })
      setForm(kind === "calendar_entry" ? (item.kind === "reminder" ? "reminder" : "event") : kind as FormKind)
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut deschide elementul.") }
    finally { setBusy(false) }
  }

  async function remove(kind: string, id: string, version: number) {
    if (!window.confirm("Ștergi acest element?")) return
    setBusy(true); setError("")
    try {
      const result = await api.remove(kind, id, version)
      setStatus(result.message); await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut șterge.") }
    finally { setBusy(false) }
  }

  async function sendCapture() {
    if (!captureText.trim()) return
    setBusy(true); setError("")
    try {
      const captured = await api.capture(captureText.trim())
      setCaptureText("")
      setCaptureProgress({ id: captured.id, status: "captured", receipt: null })
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut păstra mesajul.") }
    finally { setBusy(false) }
  }

  async function sendPhoto(file: File | undefined) {
    if (!file) return
    setBusy(true); setError("")
    try {
      const captured = await api.photo(file, captureText.trim())
      setCaptureText("")
      setCaptureProgress({ id: captured.id, status: "captured", receipt: null })
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut păstra fotografia.") }
    finally { setBusy(false) }
  }

  async function submitForm(event: React.FormEvent) {
    event.preventDefault()
    if (!form) return
    const at = fields.at ? new Date(fields.at).toISOString() : new Date().toISOString()
    let type = ""; let data: Record<string, unknown> = {}
    if (form === "project") { type = "create_project"; data = { name: fields.name, ...(editing ? { status: fields.projectStatus || "active" } : {}) } }
    if (form === "task") { type = "create_task"; data = { title: fields.title, project_id: fields.project || null, due_at: fields.at ? at : null } }
    if (form === "event" || form === "reminder") { type = "create_calendar_entry"; data = {
      kind: form, title: fields.title, starts_at: at,
      alert_offsets_minutes: editing ? JSON.parse(fields.alerts || "[]") : form === "event" ? [30, 0] : [0],
      followup_evening: form === "reminder" && fields.followup === "yes",
    } }
    if (form === "expense") { type = "log_expense"; data = { amount: fields.amount, currency: "RON", category: fields.category || null, category_override: Boolean(fields.category?.trim()), merchant: fields.merchant || null, description: fields.title || null, spent_at: at } }
    if (form === "workout") { type = "log_workout"; data = { activity: fields.title, duration_minutes: Number(fields.minutes), started_at: at, exercises: exercises.filter(item => item.name.trim()).map(item => ({ name: item.name.trim(), sets: item.sets ? Number(item.sets) : null, reps: item.reps ? Number(item.reps) : null, weight_kg: item.weight_kg ? Number(item.weight_kg) : null })) } }
    if (form === "meal") { type = "log_meal"; data = { eaten_at: at, description: fields.title, items: mealItems.map(item => ({ name: item.name, grams: item.grams ? Number(item.grams) : null, calories: item.calories ? Number(item.calories) : null, protein_g: item.protein_g ? Number(item.protein_g) : null, carbs_g: item.carbs_g ? Number(item.carbs_g) : null, fat_g: item.fat_g ? Number(item.fat_g) : null })), estimate_source: editing ? "manual" : "text" } }
    if (form === "health") { type = "log_health"; data = editing ? {
      log_date: fields.healthDate, sleep_hours: fields.sleep_hours ? Number(fields.sleep_hours) : null,
      sleep_quality: fields.sleep_quality || null, water_ml: fields.water_ml ? Number(fields.water_ml) : null,
      weight_kg: fields.weight_kg ? Number(fields.weight_kg) : null, cigarettes: fields.cigarettes ? Number(fields.cigarettes) : null,
      notes: fields.notes || null,
    } : {
      log_date: fields.healthDate || isoLocalDate(new Date()), sleep_hours: fields.sleep_hours ? Number(fields.sleep_hours) : null,
      sleep_quality: fields.sleep_quality || null, water_ml_delta: fields.water_ml ? Number(fields.water_ml) : null,
      weight_kg: fields.weight_kg ? Number(fields.weight_kg) : null, cigarettes_delta: fields.cigarettes ? Number(fields.cigarettes) : null,
      notes: fields.notes || null,
    } }
    if (editing) {
      setBusy(true); setError("")
      try {
        const result = await api.edit(editing.kind, editing.id, editing.version, data)
        setStatus(result.message)
        if (result.status === "saved") { setForm(null); setEditing(null); setFields({}); await reload() }
      } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut modifica.") }
      finally { setBusy(false) }
    } else await act(type, data)
  }

  const grouped = useMemo(() => {
    const result: Record<string, Entry[]> = {}
    for (const entry of entries) (result[isoLocalDate(new Date(entry.starts_at))] ??= []).push(entry)
    return Object.entries(result).sort(([a], [b]) => a.localeCompare(b))
  }, [entries])
  const calendarCounts = useMemo(() => Object.fromEntries(grouped.map(([day, items]) => [day, items.length])), [grouped])
  const visibleCalendarDays = showFullMonth ? grouped : grouped.filter(([day]) => day === selectedCalendarDay)
  const calendarWeekOffset = (new Date(month.getFullYear(), month.getMonth(), 1).getDay() + 6) % 7
  function moveMonth(direction: number) {
    const next = new Date(month.getFullYear(), month.getMonth() + direction, 1)
    setMonth(next)
    setSelectedCalendarDay(isoLocalDate(next))
    setShowFullMonth(false)
  }

  return <div className="app-shell">
    <div className="ambient ambient-one" /><div className="ambient ambient-two" /><div className="ambient ambient-three" />
    <main className="app-content">
      {!telegram?.initData ? <section className="glass notice"><h1>Lora</h1><p>Deschide Mini App din conversația Telegram cu Lora.</p></section> : <>
        <header className="page-heading">
          <span className="eyebrow">LORA · {tab === "today" ? "ZIUA TA" : tabs.find(item => item.id === tab)?.label.toUpperCase()}</span>
          <h1>{tab === "today" ? "Azi" : tabs.find(item => item.id === tab)?.label}</h1>
          <p>{tab === "today" ? localDay(new Date().toISOString()) : tab === "calendar" ? "Evenimente, remindere și programul tău" : tab === "projects" ? "Ce ai de făcut, pe proiecte" : tab === "journal" ? "Cheltuieli, mese și mișcare" : "Programul calendaristic al facultății"}</p>
        </header>

        {status && <div className="toast" role="status"><span>{status}</span><button aria-label="Închide mesajul" onClick={() => setStatus("")}><X size={16} /></button></div>}
        {error && <div className="error" role="alert">{error} <button onClick={() => void reload()}>Reîncearcă</button></div>}

        {tab === "today" && <>
          {appleConflicts.length > 0 && <section className="glass section-card"><div className="section-title"><Bell size={18} /><h2>Modificări de comparat</h2></div>{appleConflicts.map(conflict => <div className="proposal-row" key={conflict.id}><p>Apple Reminders și Lora au versiuni diferite pentru „{conflict.local_title || "un element"}”.</p><button className="text-action" disabled={busy} onClick={() => void inspectAppleConflict(conflict.id)}>Compară versiunile</button>{openAppleConflict?.id === conflict.id && <div className="conflict-detail"><p><strong>Lora:</strong> {openAppleConflict.detail.local?.title || "element indisponibil"}{openAppleConflict.detail.local?.at ? ` · ${localDay(openAppleConflict.detail.local.at)} ${hour(openAppleConflict.detail.local.at)}` : ""}</p><p><strong>Apple:</strong> {openAppleConflict.detail.apple_deleted ? "element șters" : `${openAppleConflict.detail.apple?.title || ""}${openAppleConflict.detail.apple?.at ? ` · ${localDay(openAppleConflict.detail.apple.at)} ${hour(openAppleConflict.detail.apple.at)}` : ""}`}</p><div className="inline-actions"><button disabled={busy} onClick={() => void resolveApple(conflict.id, "keep_local")}>Păstrează Lora</button><button disabled={busy} onClick={() => void resolveApple(conflict.id, "use_apple")}>Preia Apple</button></div></div>}</div>)}</section>}
          {proposals.length > 0 && <section className="glass section-card"><div className="section-title"><Sparkles size={18} /><h2>De decis</h2></div>{proposals.map(proposal => <div className="proposal-row" key={proposal.id}><p>{proposal.reason}</p><div className="inline-actions">{proposal.source.startsWith("followup:") ? <><button disabled={busy} onClick={() => void decideFollowup(proposal.id, "done")}>Am făcut</button><button disabled={busy} onClick={() => void decideFollowup(proposal.id, "tomorrow")}>Mută pe mâine</button></> : <><button disabled={busy} onClick={() => void decide(proposal.id, true)}>Da, fă asta</button><button disabled={busy} onClick={() => void decide(proposal.id, false)}>Nu acum</button></>}</div></div>)}</section>}
          <section className="glass capture-panel">
            <div className="section-title"><Sparkles size={18} /><h2>Spune-i Lorei</h2></div>
            <div className="capture-row"><textarea aria-label="Ce vrei să rețină Lora?" placeholder="De exemplu: mâine sun administratorul, azi am cheltuit 15 lei la cantină…" value={captureText} onChange={event => setCaptureText(event.target.value)} rows={2} /><label className="photo-action" aria-label="Adaugă fotografie cu mâncarea"><Camera size={19} /><input type="file" accept="image/*" capture="environment" disabled={busy} onChange={event => { void sendPhoto(event.target.files?.[0]); event.target.value = "" }} /></label><button className="circle-action" aria-label="Trimite către Lora" disabled={busy || !captureText.trim()} onClick={() => void sendCapture()}><Send size={19} /></button></div>
            {captureProgress && <div className="capture-result" role="status" aria-live="polite"><p>{captureProgress.receipt || (captureProgress.status === "failed" ? "Nu am putut procesa mesajul încă. Reîncerc automat." : captureProgress.status === "processed" || captureProgress.status === "needs_input" ? "Pregătesc răspunsul…" : "Lora procesează mesajul…")}</p><button type="button" aria-label="Închide rezultatul" onClick={() => setCaptureProgress(null)}><X size={16} /></button></div>}
          </section>
          <div className="quick-actions"><button onClick={() => setForm("task")}><Plus size={16} /> Task</button><button onClick={() => setForm("reminder")}><Bell size={16} /> Reminder</button><button onClick={() => setForm("expense")}><Wallet size={16} /> Cheltuială</button></div>
          <div className="two-column">
            <section className="glass section-card"><div className="section-title"><CalendarDays size={19} /><h2>Ce urmează</h2></div>{!today ? <Empty>Se încarcă programul…</Empty> : today.entries.length ? today.entries.map(item => <EntryRow key={item.id} entry={item} done={item.kind === "reminder" ? () => void act("complete_entry", { entry_id: item.id, expected_version: item.version }) : undefined} edit={() => void openEdit("calendar_entry",item.id)} remove={() => void remove("calendar_entry",item.id,item.version)} />) : <Empty>Ziua este liberă. Adaugă ce contează.</Empty>}</section>
            <section className="glass section-card"><div className="section-title"><Check size={19} /><h2>De făcut</h2></div>{!today ? <Empty>Se încarcă taskurile…</Empty> : today.tasks.length ? today.tasks.slice(0, 6).map(task => <TaskRow key={task.id} task={task} done={() => void act("complete_task", { task_id: task.id, expected_version: task.version })} edit={() => void openEdit("task",task.id)} remove={() => void remove("task",task.id,task.version)} />) : <Empty>Nu ai taskuri de făcut acum.</Empty>}</section>
          </div>
        </>}

        {tab === "calendar" && <section className="glass section-card"><div className="section-title month-title"><CalendarDays size={19} /><h2>{month.toLocaleDateString("ro-RO", { month: "long", year: "numeric" })}</h2><span className="month-controls"><button aria-label="Luna anterioară" onClick={() => moveMonth(-1)}><ChevronLeft size={18} /></button><button aria-label="Luna următoare" onClick={() => moveMonth(1)}><ChevronRight size={18} /></button></span></div>
          <div className="month-grid">{["Lu", "Ma", "Mi", "Jo", "Vi", "Sâ", "Du"].map(day => <span className="month-weekday" key={day}>{day}</span>)}{Array.from({ length: calendarWeekOffset }, (_, index) => <span className="month-blank" key={`blank-${index}`} aria-hidden="true" />)}{Array.from({ length: new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate() }, (_, index) => {
            const date = new Date(month.getFullYear(), month.getMonth(), index + 1)
            const day = isoLocalDate(date)
            const count = calendarCounts[day] || 0
            return <button type="button" key={day} className={`month-day ${day === isoLocalDate(new Date()) ? "is-today" : ""} ${day === selectedCalendarDay && !showFullMonth ? "is-selected" : ""}`} aria-label={`${localDay(`${day}T12:00:00`)}${count ? `, ${count} ${count === 1 ? "element" : "elemente"}` : ""}`} aria-pressed={day === selectedCalendarDay && !showFullMonth} onClick={() => { setSelectedCalendarDay(day); setShowFullMonth(false) }}><span>{index + 1}</span>{count > 0 && <i aria-hidden="true" />}</button>
          })}</div>
          <button type="button" className="text-action month-view-toggle" onClick={() => setShowFullMonth(!showFullMonth)}>{showFullMonth ? "Vezi ziua selectată" : "Vezi toată luna"}</button>
          {visibleCalendarDays.length ? visibleCalendarDays.map(([date, items]) => <div className="day-group" key={date}><h3>{localDay(`${date}T12:00:00`)}</h3>{items.map(item => <EntryRow key={item.id} entry={item} done={item.kind === "reminder" ? () => void act("complete_entry", { entry_id: item.id, expected_version: item.version }) : undefined} edit={() => void openEdit("calendar_entry",item.id)} remove={() => void remove("calendar_entry",item.id,item.version)} />)}</div>) : <Empty>{showFullMonth ? "Nu sunt evenimente în această lună." : `Nimic planificat pentru ${localDay(`${selectedCalendarDay}T12:00:00`)}.`}</Empty>}
          <div className="inline-actions"><button onClick={() => setForm("event")}><Plus size={16} /> Eveniment</button><button onClick={() => setForm("reminder")}><Plus size={16} /> Reminder</button></div>
        </section>}

        {tab === "projects" && <section className="glass section-card"><div className="section-title"><Check size={19} /><h2>Taskuri pe proiecte</h2></div>{projects.map(project => <div className="project-group" key={project.id}><div className="group-head"><h3>{project.name}</h3><button aria-label={`Editează proiectul ${project.name}`} onClick={() => void openEdit("project",project.id)}><Pencil size={14} /></button><button aria-label={`Șterge proiectul ${project.name}`} onClick={() => void remove("project",project.id,project.version)}><Trash2 size={14} /></button></div>{tasks.filter(task => task.project_id === project.id && task.status === "pending").map(task => <TaskRow key={task.id} task={task} done={() => void act("complete_task", { task_id: task.id, expected_version: task.version })} edit={() => void openEdit("task",task.id)} remove={() => void remove("task",task.id,task.version)} />)}</div>)}<div className="project-group"><h3>Fără proiect</h3>{tasks.filter(task => !task.project_id && task.status === "pending").map(task => <TaskRow key={task.id} task={task} done={() => void act("complete_task", { task_id: task.id, expected_version: task.version })} edit={() => void openEdit("task",task.id)} remove={() => void remove("task",task.id,task.version)} />)}</div>{!tasks.length && <Empty>Nu ai încă taskuri.</Empty>}<div className="inline-actions"><button onClick={() => setForm("task")}><Plus size={16} /> Task</button><button onClick={() => setForm("project")}><Plus size={16} /> Proiect</button></div></section>}

        {tab === "journal" && <div className="journal-grid"><section className="glass section-card"><div className="section-title"><Wallet size={19} /><h2>Cheltuieli</h2></div>{journal?.expenses.length ? journal.expenses.slice(0, 8).map(item => <div className="simple-row" key={item.id}><span><strong>{item.merchant || item.description || item.category}</strong><small>{item.category} · {localDay(item.spent_at)}</small></span><b>{item.amount} {item.currency}</b><RowActions edit={() => void openEdit("expense",item.id)} remove={() => void remove("expense",item.id,item.version)} /></div>) : <Empty>Nicio cheltuială încă.</Empty>}<button className="text-action" onClick={() => setForm("expense")}>+ Adaugă cheltuială</button></section><MealPanel meals={journal?.meals || []} onAdd={() => { setFields({}); setEditing(null); setMealItems([blankMealItem()]); setForm("meal") }} onEdit={id => void openEdit("meal", id)} onRemove={(id, version) => void remove("meal", id, version)} /><section className="glass section-card"><div className="section-title"><Dumbbell size={19} /><h2>Antrenamente</h2></div>{journal?.workouts.length ? journal.workouts.slice(0, 8).map(item => <div className="simple-row" key={item.id}><span><strong>{item.activity}</strong><small>{localDay(item.started_at)}</small></span><b>{item.duration_minutes} min</b><RowActions edit={() => void openEdit("workout",item.id)} remove={() => void remove("workout",item.id,item.version)} /></div>) : <Empty>Niciun antrenament încă.</Empty>}<button className="text-action" onClick={() => {setExercises([]);setForm("workout")}}>+ Adaugă antrenament</button></section><section className="glass section-card"><div className="section-title"><HeartPulse size={19} /><h2>Sănătate</h2></div>{journal?.health.length ? journal.health.slice(0, 8).map(item => <div className="simple-row" key={item.id}><span><strong>{item.log_date}</strong><small>{[item.sleep_hours ? `${item.sleep_hours}h somn` : "", item.water_ml ? `${item.water_ml} ml apă` : "", item.weight_kg ? `${item.weight_kg} kg` : ""].filter(Boolean).join(" · ") || item.notes || "Jurnal sănătate"}</small></span><RowActions edit={() => void openEdit("health",item.id)} remove={() => void remove("health",item.id,item.version)} /></div>) : <Empty>Nu ai înregistrări de sănătate.</Empty>}<button className="text-action" onClick={() => {setFields({healthDate:isoLocalDate(new Date())});setEditing(null);setForm("health")}}>+ Adaugă sănătate</button></section></div>}

        {tab === "journal" && <IncomePanel />}
        {tab === "university" && <UniversityPanel />}

        {form && <form className="glass inline-form" onSubmit={event => void submitForm(event)}><div className="section-title"><Plus size={18} /><h2>{editing ? "Editează" : ({ task: "Task nou", project: "Proiect nou", event: "Eveniment nou", reminder: "Reminder nou", expense: "Cheltuială nouă", workout: "Antrenament nou", meal: "Masă nouă", health: "Sănătate" } as const)[form]}</h2><button className="close-form" type="button" aria-label="Închide formularul" onClick={() => {setForm(null);setEditing(null)}}><X size={18} /></button></div>
          {form === "project" ? <label>Nume<input required value={fields.name || ""} onChange={event => setFields({ ...fields, name: event.target.value })} /></label> : form !== "health" && <label>{form === "expense" ? "Descriere" : form === "workout" ? "Tip antrenament" : "Titlu"}<input required={form !== "expense"} value={fields.title || ""} onChange={event => setFields({ ...fields, title: event.target.value })} /></label>}
          {(form === "task") && <label>Proiect<select value={fields.project || ""} onChange={event => setFields({ ...fields, project: event.target.value })}><option value="">Fără proiect</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>}
          {form === "expense" && <><label>Sumă (lei)<input type="number" min="0.01" step="0.01" required value={fields.amount || ""} onChange={event => setFields({ ...fields, amount: event.target.value })} /></label><label>Loc / comerciant<input value={fields.merchant || ""} onChange={event => setFields({ ...fields, merchant: event.target.value })} /></label><label>Categorie<input placeholder="mâncare, transport…" value={fields.category || ""} onChange={event => setFields({ ...fields, category: event.target.value })} /></label></>}
          {form === "workout" && <label>Durată (minute)<input type="number" min="1" required value={fields.minutes || ""} onChange={event => setFields({ ...fields, minutes: event.target.value })} /></label>}
          {form === "workout" && <div className="meal-editor"><p>Exerciții (opțional)</p>{exercises.map((item, index) => <div className="meal-item" key={index}><label>Exercițiu<input required value={item.name} onChange={event => setExercises(exercises.map((old, i) => i === index ? { ...old, name: event.target.value } : old))} /></label><label>Seturi<input type="number" min="1" value={item.sets} onChange={event => setExercises(exercises.map((old, i) => i === index ? { ...old, sets: event.target.value } : old))} /></label><label>Repetări<input type="number" min="1" value={item.reps} onChange={event => setExercises(exercises.map((old, i) => i === index ? { ...old, reps: event.target.value } : old))} /></label><label>Greutate kg<input type="number" min="0" step="0.5" value={item.weight_kg} onChange={event => setExercises(exercises.map((old, i) => i === index ? { ...old, weight_kg: event.target.value } : old))} /></label><button type="button" className="text-action" onClick={() => setExercises(exercises.filter((_, i) => i !== index))}>Elimină exercițiul</button></div>)}<button type="button" className="text-action" onClick={() => setExercises([...exercises, blankExercise()])}>+ Adaugă exercițiu</button></div>}
          {form === "meal" && <div className="meal-editor"><p>Alimente și valori estimate</p>{mealItems.map((item, index) => <div className="meal-item" key={index}><label>Aliment<input required value={item.name} onChange={event => setMealItems(mealItems.map((old, i) => i === index ? { ...old, name: event.target.value } : old))} /></label><label>Grame<input type="number" min="1" value={item.grams} onChange={event => setMealItems(mealItems.map((old, i) => i === index ? { ...old, grams: event.target.value } : old))} /></label><label>kcal<input type="number" min="0" value={item.calories} onChange={event => setMealItems(mealItems.map((old, i) => i === index ? { ...old, calories: event.target.value } : old))} /></label><label>Proteine g<input type="number" min="0" value={item.protein_g} onChange={event => setMealItems(mealItems.map((old, i) => i === index ? { ...old, protein_g: event.target.value } : old))} /></label><label>Carbo g<input type="number" min="0" value={item.carbs_g} onChange={event => setMealItems(mealItems.map((old, i) => i === index ? { ...old, carbs_g: event.target.value } : old))} /></label><label>Grăsimi g<input type="number" min="0" value={item.fat_g} onChange={event => setMealItems(mealItems.map((old, i) => i === index ? { ...old, fat_g: event.target.value } : old))} /></label>{mealItems.length > 1 && <button type="button" className="text-action" onClick={() => setMealItems(mealItems.filter((_, i) => i !== index))}>Elimină aliment</button>}</div>)}<button type="button" className="text-action" onClick={() => setMealItems([...mealItems, blankMealItem()])}>+ Adaugă aliment</button></div>}
          {form === "health" && <div className="health-editor"><label>Data<input type="date" required value={fields.healthDate || isoLocalDate(new Date())} onChange={event => setFields({ ...fields, healthDate: event.target.value })} /></label><label>Somn (ore)<input type="number" min="0" max="24" step="0.25" value={fields.sleep_hours || ""} onChange={event => setFields({ ...fields, sleep_hours: event.target.value })} /></label><label>Calitatea somnului<select value={fields.sleep_quality || ""} onChange={event => setFields({ ...fields, sleep_quality: event.target.value })}><option value="">Nespecificat</option><option value="great">Foarte bună</option><option value="good">Bună</option><option value="neutral">Mediu</option><option value="bad">Slabă</option><option value="terrible">Foarte slabă</option></select></label><label>Apă (ml){!editing && " · adăugată acum"}<input type="number" min="0" value={fields.water_ml || ""} onChange={event => setFields({ ...fields, water_ml: event.target.value })} /></label><label>Greutate (kg)<input type="number" min="1" step="0.1" value={fields.weight_kg || ""} onChange={event => setFields({ ...fields, weight_kg: event.target.value })} /></label><label>Țigări{!editing && " · adăugate acum"}<input type="number" min="0" value={fields.cigarettes || ""} onChange={event => setFields({ ...fields, cigarettes: event.target.value })} /></label><label>Notițe<input value={fields.notes || ""} onChange={event => setFields({ ...fields, notes: event.target.value })} /></label></div>}
          {form !== "project" && form !== "health" && <label>{form === "task" ? "Termen (opțional)" : "Când"}<input type="datetime-local" required={form === "event" || form === "reminder"} value={fields.at || ""} onChange={event => setFields({ ...fields, at: event.target.value })} /></label>}
          {form === "reminder" && <label className="checkbox-label"><input type="checkbox" checked={fields.followup === "yes"} onChange={event => setFields({ ...fields, followup: event.target.checked ? "yes" : "no" })} /> Întreabă-mă seara dacă nu l-am făcut</label>}
          <button className="primary" type="submit" disabled={busy}>Salvează</button>
        </form>}
      </>}
    </main>
    {telegram?.initData && <nav className="bottom-nav" aria-label="Navigație principală">{tabs.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? "active" : ""} aria-current={tab === id ? "page" : undefined} onClick={() => { setTab(id); setForm(null) }}><Icon size={20} strokeWidth={1.8} /><span>{label}</span></button>)}</nav>}
  </div>
}

function RowActions({ edit, remove }: { edit: () => void; remove: () => void }) { return <span className="row-actions"><button aria-label="Editează" onClick={edit}><Pencil size={14} /></button><button aria-label="Șterge" onClick={remove}><Trash2 size={14} /></button></span> }
function EntryRow({ entry, done, edit, remove }: { entry: Entry; done?: () => void; edit?: () => void; remove?: () => void }) { return <div className={`agenda-row kind-${entry.kind}`}><span className="agenda-time">{hour(entry.starts_at)}</span><span className="agenda-line" /><span className="agenda-text"><strong>{entry.title}</strong><small>{entry.kind === "academic" ? "Facultate · editează în Facultate" : entry.kind === "reminder" ? "Reminder" : "Eveniment"}</small></span>{done ? <button className="entry-done" onClick={done} aria-label={`Marchează ${entry.title} ca făcut`}><Check size={16} /></button> : entry.kind === "reminder" && <Bell size={16} />}{entry.kind !== "academic" && edit && remove && <RowActions edit={edit} remove={remove} />}</div> }
function TaskRow({ task, done, edit, remove }: { task: Task; done: () => void; edit: () => void; remove: () => void }) { return <div className="task-row"><button aria-label={`Marchează ${task.title} ca făcut`} className="task-check" onClick={done}><Check size={14} /></button><span><strong>{task.title}</strong><small>{task.project_name || (task.due_at ? localDay(task.due_at) : "Fără termen")}</small></span><RowActions edit={edit} remove={remove} /></div> }
