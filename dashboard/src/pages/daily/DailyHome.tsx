import { useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { ArrowRight, Bell, CalendarDays, Check, ChevronRight, Clock3, FolderKanban, GraduationCap, Plus, Wallet, Utensils, Dumbbell, ListChecks, Ellipsis } from "lucide-react"
import { fetchWeek } from "../../api/queries/calendar"
import { fetchTasks, updateTask } from "../../api/queries/tasks"
import { fetchProjects } from "../../api/queries/projects"
import type { CalendarEvent, CalendarScheduleEntry, Task } from "../../types"
import { localDate, shortTime } from "./date"
import { LoginRequired } from "./LoginRequired"
import { isUnauthorized } from "./isUnauthorized"

type AgendaItem = { key: string; title: string; time: string; detail?: string; kind: "event" | "reminder" | "class" }

function todayAgenda(events: CalendarEvent[], classes: CalendarScheduleEntry[]): AgendaItem[] {
  return [
    ...events.map((item) => ({ key: `event-${item.id}`, title: item.title, time: shortTime(item.event_time), detail: item.description, kind: item.event_type === "reminder" ? "reminder" as const : "event" as const })),
    ...classes.map((item) => ({ key: `class-${item.id}`, title: item.subject_name, time: shortTime(item.start_time), detail: [item.class_type, item.room].filter(Boolean).join(" · "), kind: "class" as const })),
  ].sort((a, b) => (a.time || "99:99").localeCompare(b.time || "99:99"))
}

export default function DailyHome() {
  const [quickAddOpen, setQuickAddOpen] = useState(false)
  const [now, setNow] = useState(() => new Date())
  useEffect(() => { const timer = window.setInterval(() => setNow(new Date()), 60_000); return () => window.clearInterval(timer) }, [])
  const queryClient = useQueryClient()
  const date = localDate(now)
  const calendar = useQuery({ queryKey: ["calendar", "daily", date], queryFn: () => fetchWeek(now) })
  const tasks = useQuery({ queryKey: ["tasks", "daily"], queryFn: () => fetchTasks("pending") })
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects })
  const complete = useMutation({
    mutationFn: (id: number) => updateTask(id, { status: "done" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  })

  const today = calendar.data?.find((item) => item.date === date)
  const agenda = todayAgenda(today?.events ?? [], today?.schedule ?? [])
  const dueTasks = (tasks.data ?? []).filter((item) => item.status !== "done" && item.due_date && item.due_date.slice(0, 10) <= date)
  const upcomingTasks = (tasks.data ?? []).filter((item) => item.status !== "done" && !!item.due_date && item.due_date.slice(0, 10) > date).slice(0, 3)
  const dateTitle = now.toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" })
  if (isUnauthorized(calendar.error, tasks.error, projects.error)) return <LoginRequired />

  return <div className="daily-page">
    <div className="daily-page-heading">
      <div><p className="daily-eyebrow">ZIUA TA</p><h1>Azi</h1><p className="daily-subtitle">{dateTitle}</p></div>
      <button type="button" className="daily-primary-button" onClick={() => setQuickAddOpen((open) => !open)} aria-expanded={quickAddOpen}><Plus size={17} /> Adaugă</button>
    </div>
    {quickAddOpen && <div className="daily-panel daily-quick-add" aria-label="Adăugare rapidă">
      <Link to="/projects?action=task"><ListChecks size={17} /> Task</Link>
      <Link to="/calendar?action=reminder"><Bell size={17} /> Reminder</Link>
      <Link to="/calendar?action=event"><CalendarDays size={17} /> Eveniment</Link>
      <Link to="/journal?action=expense"><Wallet size={17} /> Cheltuială</Link>
      <Link to="/nutrition"><Utensils size={17} /> Masă</Link>
      <Link to="/journal?action=workout"><Dumbbell size={17} /> Antrenament</Link>
    </div>}

    <div className="daily-home-grid">
      <section className="daily-panel daily-feature-panel">
        <div className="daily-section-heading"><div><p className="daily-eyebrow">ÎN ORDINEA ZILEI</p><h2>Ce urmează</h2></div><Link to="/calendar" aria-label="Deschide calendarul"><ArrowRight size={18} /></Link></div>
        {calendar.isPending ? <p className="daily-state">Se încarcă programul…</p> : calendar.isError ? <p className="daily-state daily-error">Calendarul nu a putut fi încărcat. <button type="button" onClick={() => calendar.refetch()}>Reîncearcă</button></p> : agenda.length === 0 ? <p className="daily-state">Nu ai evenimente sau cursuri astăzi.</p> : <div className="daily-agenda-list">{agenda.map((item) => <div className={`daily-agenda-item daily-${item.kind}`} key={item.key}>
          <span className="daily-agenda-time">{item.time || "Toată ziua"}</span><span className="daily-agenda-line" aria-hidden="true" /><span className="daily-agenda-content"><strong>{item.title}</strong><small>{item.detail || (item.kind === "reminder" ? "Reminder" : item.kind === "class" ? "Facultate" : "Eveniment")}</small></span>
          {item.kind === "reminder" ? <Bell size={16} /> : item.kind === "class" ? <GraduationCap size={16} /> : <CalendarDays size={16} />}
        </div>)}</div>}
      </section>

      <section className="daily-panel">
        <div className="daily-section-heading"><div><p className="daily-eyebrow">DE REZOLVAT</p><h2>Taskuri</h2></div><Link to="/projects" aria-label="Vezi toate taskurile"><ArrowRight size={18} /></Link></div>
        {tasks.isPending ? <p className="daily-state">Se încarcă taskurile…</p> : tasks.isError ? <p className="daily-state daily-error">Taskurile nu au putut fi încărcate. <button type="button" onClick={() => tasks.refetch()}>Reîncearcă</button></p> : <>
          {dueTasks.length === 0 ? <p className="daily-state">Nu ai taskuri scadente astăzi.</p> : dueTasks.slice(0, 5).map((task: Task) => <div className="daily-task-row" key={task.id}>
            <button type="button" className="daily-check" onClick={() => complete.mutate(task.id)} disabled={complete.isPending} aria-label={`Marchează ${task.title} ca terminat`}><Check size={14} /></button>
            <span className="daily-task-text"><strong>{task.title}</strong><small>{task.subject_name || task.project_name || (task.due_date && task.due_date.slice(0, 10) < date ? "Restant" : "Astăzi")}</small></span>
          </div>)}
          {upcomingTasks.length > 0 && <><p className="daily-list-divider">URMEAZĂ</p>{upcomingTasks.map((task) => <div className="daily-task-row daily-upcoming" key={task.id}><Clock3 size={16} /><span className="daily-task-text"><strong>{task.title}</strong><small>{task.subject_name || task.project_name || task.due_date?.slice(0, 10)}</small></span></div>)}</>}
        </>}
        {complete.isError && <p className="daily-inline-error">Taskul nu a putut fi actualizat.</p>}
        <Link className="daily-panel-link" to="/projects">Toate taskurile <ChevronRight size={16} /></Link>
      </section>
    </div>

    <div className="daily-quick-grid">
      <Link className="daily-quick-card" to="/calendar"><CalendarDays size={20} /><span><strong>Calendar</strong><small>Evenimente, remindere și orar</small></span><ChevronRight size={17} /></Link>
      <Link className="daily-quick-card" to="/projects"><FolderKanban size={20} /><span><strong>Proiecte</strong><small>{projects.isError ? "Nu s-au putut încărca" : projects.data ? `${projects.data.filter((item) => item.status === "active").length} active` : "Se încarcă…"}</small></span><ChevronRight size={17} /></Link>
      <Link className="daily-quick-card" to="/more"><Ellipsis size={20} /><span><strong>Mai mult</strong><small>Celelalte instrumente</small></span><ChevronRight size={17} /></Link>
    </div>
  </div>
}
