import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { GraduationCap, ChevronDown, Plus, Clock, MapPin } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"
import type { UniversitySubject } from "../types"

export default function University() {
  const [view, setView] = useState("Overview")
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState("")
  const [name, setName] = useState("")
  const [professor, setProfessor] = useState("")
  const [credits, setCredits] = useState("")
  const [gradeSubject, setGradeSubject] = useState("")
  const [gradeValue, setGradeValue] = useState("")
  const [gradeType, setGradeType] = useState("exam")
  const [gradeWeight, setGradeWeight] = useState("")
  const [examSubject, setExamSubject] = useState("")
  const [examDate, setExamDate] = useState("")
  const [examType, setExamType] = useState("final")
  const [examRoom, setExamRoom] = useState("")
  const [attendanceSubject, setAttendanceSubject] = useState("")
  const [attendanceDate, setAttendanceDate] = useState("")
  const [attendancePresent, setAttendancePresent] = useState(true)
  const [uniTaskSubject, setUniTaskSubject] = useState("")
  const [uniTaskTitle, setUniTaskTitle] = useState("")
  const [uniTaskDue, setUniTaskDue] = useState("")
  const [uniProjectSubject, setUniProjectSubject] = useState("")
  const [uniProjectName, setUniProjectName] = useState("")
  const [uniProjectDescription, setUniProjectDescription] = useState("")
  const [uniProjectDeadline, setUniProjectDeadline] = useState("")
  const [scheduleSubject, setScheduleSubject] = useState("")
  const [scheduleDay, setScheduleDay] = useState("0")
  const [scheduleStart, setScheduleStart] = useState("09:00")
  const [scheduleEnd, setScheduleEnd] = useState("10:00")
  const [scheduleRoom, setScheduleRoom] = useState("")
  const [scheduleType, setScheduleType] = useState("curs")
  const [scheduleWeek, setScheduleWeek] = useState("both")
  const qc = useQueryClient()
  const addSubject = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/university/subjects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, professor, credits: credits ? Number(credits) : null }) })
      if (!response.ok) throw new Error("Nu am putut adăuga materia")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setName(""); setProfessor(""); setCredits("") },
  })
  const addGrade = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/university/grades", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_id: Number(gradeSubject), grade: Number(gradeValue), grade_type: gradeType, weight: gradeWeight ? Number(gradeWeight) : null }) })
      if (!response.ok) throw new Error("Nu am putut adăuga nota")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setGradeSubject(""); setGradeValue(""); setGradeWeight("") },
  })
  const addExam = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/university/exams", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_id: Number(examSubject), exam_date: examDate, exam_type: examType, room: examRoom || null }) })
      if (!response.ok) throw new Error("Nu am putut adăuga examenul")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setExamSubject(""); setExamDate(""); setExamRoom("") },
  })
  const addAttendance = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/university/attendance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_id: Number(attendanceSubject), class_date: attendanceDate, attended: attendancePresent }) })
      if (!response.ok) throw new Error("Nu am putut înregistra prezența")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setAttendanceSubject(""); setAttendanceDate("") },
  })
  const addUniTask = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: uniTaskTitle, due_date: uniTaskDue || null, university_subject_id: Number(uniTaskSubject) }) })
      if (!response.ok) throw new Error("Nu am putut adăuga taskul")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setUniTaskSubject(""); setUniTaskTitle(""); setUniTaskDue("") },
  })
  const addUniProject = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: uniProjectName, description: uniProjectDescription || null, deadline: uniProjectDeadline || null, university_subject_id: Number(uniProjectSubject) }) })
      if (!response.ok) throw new Error("Nu am putut adăuga proiectul")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setUniProjectSubject(""); setUniProjectName(""); setUniProjectDescription(""); setUniProjectDeadline("") },
  })
  const addSchedule = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/university/schedule", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_name: scheduleSubject, day_of_week: Number(scheduleDay), start_time: scheduleStart, end_time: scheduleEnd, room: scheduleRoom || null, class_type: scheduleType, week_type: scheduleWeek }) })
      if (!response.ok) throw new Error("Nu am putut adăuga cursul")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university-schedule"] }); setShowAdd(false); setScheduleSubject(""); setScheduleRoom("") },
  })
  const deleteSchedule = useMutation({
    mutationFn: async (id: number) => {
      const response = await fetch(`/api/university/schedule/${id}`, { method: "DELETE" })
      if (!response.ok) throw new Error("Nu am putut elimina intrarea")
      return response.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["university-schedule"] }),
  })
  const editSchedule = useMutation({
    mutationFn: async (item: any) => {
      const room = window.prompt("Sala:", item.room || "")
      if (room === null) return null
      const start = window.prompt("Ora de început (HH:MM):", String(item.start_time || "").slice(0, 5))
      if (start === null) return null
      const end = window.prompt("Ora de sfârșit (HH:MM):", String(item.end_time || "").slice(0, 5))
      if (end === null) return null
      const response = await fetch(`/api/university/schedule/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_name: item.subject_name, day_of_week: item.day_of_week, start_time: start, end_time: end, room: room || null, class_type: item.class_type || "curs", week_type: item.week_type || "both" }) })
      if (!response.ok) throw new Error("Nu am putut modifica intrarea")
      return response.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["university-schedule"] }),
  })
  const syncCalendar = useMutation({
    mutationFn: async () => { const response = await fetch("/api/university/calendar-sync", { method: "POST" }); if (!response.ok) throw new Error("Calendar indisponibil"); return response.json() },
  })
  const { data, isLoading } = useQuery<{ subjects: UniversitySubject[] }>({
    queryKey: ["university"],
    queryFn: () => fetch("/api/university/summary").then((r) => r.json()),
  })
  const { data: scheduleData } = useQuery<{ week_type?: string; items?: any[] }>({
    queryKey: ["university-schedule"],
    queryFn: () => fetch("/api/university/schedule").then((r) => r.json()),
    enabled: view === "Orar",
  })

  if (isLoading) return <Spinner className="py-12" />

  const subjects = data?.subjects ?? []
  const visibleSubjects = subjects.filter((subject: any) => subject.name.toLowerCase().includes(search.toLowerCase()) || String(subject.professor ?? "").toLowerCase().includes(search.toLowerCase()))
  const overview = (data as any)?.overview ?? {}
  const avgGrade = subjects.length
    ? (subjects.reduce((s, x) => s + (x.grade ?? 0), 0) / subjects.length).toFixed(1)
    : "-"

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="mb-6 flex items-center justify-between"><label className="relative flex w-fit items-center gap-2 text-sm font-semibold text-text-primary"><span>University · {view}</span><ChevronDown className="w-4 h-4 text-text-muted" /><select value={view} onChange={(e) => setView(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Alege secțiunea University">{["Overview", "Materii", "Note", "Prezențe", "Examene", "Taskuri", "Proiecte", "Orar"].map((item) => <option key={item}>{item}</option>)}</select></label><button type="button" onClick={() => setShowAdd((v) => !v)} className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-white" aria-label="Adaugă în University"><Plus className="w-4 h-4" /></button></div>
          {view !== "Orar" && <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Caută în University…" className="mb-5 w-full rounded-xl border border-border bg-transparent px-3 py-2 text-sm text-text-primary outline-none focus:border-primary" />}
          {showAdd && view === "Orar" && <div className="mb-6 rounded-2xl border border-border bg-surface/70 p-4">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <input value={scheduleSubject} onChange={(e) => setScheduleSubject(e.target.value)} placeholder="Materia" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" />
              <select value={scheduleDay} onChange={(e) => setScheduleDay(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm">{["Luni", "Marți", "Miercuri", "Joi", "Vineri"].map((day, i) => <option key={day} value={i}>{day}</option>)}</select>
              <input value={scheduleStart} onChange={(e) => setScheduleStart(e.target.value)} type="time" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" />
              <input value={scheduleEnd} onChange={(e) => setScheduleEnd(e.target.value)} type="time" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" />
              <input value={scheduleRoom} onChange={(e) => setScheduleRoom(e.target.value)} placeholder="Sală (opțional)" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" />
              <select value={scheduleType} onChange={(e) => setScheduleType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="curs">Curs</option><option value="seminar">Seminar</option><option value="laborator">Laborator</option><option value="curs+seminars">Curs + seminar</option></select>
              <select value={scheduleWeek} onChange={(e) => setScheduleWeek(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="both">În fiecare săptămână</option><option value="odd">Săptămâni impare</option><option value="even">Săptămâni pare</option></select>
            </div>
            <div className="mt-3 flex gap-2"><button type="button" onClick={() => setShowAdd(false)} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary">Anulează</button><button type="button" onClick={() => addSchedule.mutate()} disabled={!scheduleSubject.trim() || addSchedule.isPending} className="rounded-xl bg-primary px-3 py-2 text-xs text-white">Adaugă în orar</button></div>
          </div>}
          {showAdd && view !== "Orar" && <div className="mb-6 rounded-2xl border border-border bg-surface/70 p-4">
            <p className="mb-3 text-sm font-semibold">Adaugă {view === "Materii" || view === "Overview" ? "materie" : view === "Note" ? "notă" : view === "Examene" ? "examen" : view === "Prezențe" ? "prezență" : view === "Taskuri" ? "task" : "proiect"}</p>
            {(view === "Materii" || view === "Overview") && <div className="grid gap-2 sm:grid-cols-3"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nume materie" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><input value={professor} onChange={(e) => setProfessor(e.target.value)} placeholder="Profesor" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><input value={credits} onChange={(e) => setCredits(e.target.value)} placeholder="Credite" type="number" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div>}
            {view === "Note" && <div className="grid gap-2 sm:grid-cols-4"><select value={gradeSubject} onChange={(e) => setGradeSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><input value={gradeValue} onChange={(e) => setGradeValue(e.target.value)} placeholder="Nota" type="number" min="1" max="10" step="0.01" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><select value={gradeType} onChange={(e) => setGradeType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="exam">Examen</option><option value="partial">Test</option><option value="proiect">Proiect</option></select><input value={gradeWeight} onChange={(e) => setGradeWeight(e.target.value)} placeholder="Pondere %" type="number" min="0" max="100" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div>}
            {view === "Examene" && <div className="grid gap-2 sm:grid-cols-4"><select value={examSubject} onChange={(e) => setExamSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><input value={examDate} onChange={(e) => setExamDate(e.target.value)} type="date" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><select value={examType} onChange={(e) => setExamType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="final">Examen</option><option value="partial">Test</option><option value="colocviu">Colocviu</option></select><input value={examRoom} onChange={(e) => setExamRoom(e.target.value)} placeholder="Sală" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div>}
            {view === "Prezențe" && <div className="grid gap-2 sm:grid-cols-3"><select value={attendanceSubject} onChange={(e) => setAttendanceSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><input value={attendanceDate} onChange={(e) => setAttendanceDate(e.target.value)} type="date" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><select value={attendancePresent ? "present" : "absent"} onChange={(e) => setAttendancePresent(e.target.value === "present")} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="present">Prezent</option><option value="absent">Absent</option></select></div>}
            {(view === "Taskuri" || view === "Proiecte") && <div className="grid gap-2 sm:grid-cols-3"><select value={view === "Taskuri" ? uniTaskSubject : uniProjectSubject} onChange={(e) => view === "Taskuri" ? setUniTaskSubject(e.target.value) : setUniProjectSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><input value={view === "Taskuri" ? uniTaskTitle : uniProjectName} onChange={(e) => view === "Taskuri" ? setUniTaskTitle(e.target.value) : setUniProjectName(e.target.value)} placeholder={view === "Taskuri" ? "Task" : "Nume proiect"} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><input value={view === "Taskuri" ? uniTaskDue : uniProjectDeadline} onChange={(e) => view === "Taskuri" ? setUniTaskDue(e.target.value) : setUniProjectDeadline(e.target.value)} type="date" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div>}
            <div className="mt-3 flex gap-2"><button type="button" onClick={() => setShowAdd(false)} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary">Anulează</button><button type="button" onClick={() => view === "Note" ? addGrade.mutate() : view === "Examene" ? addExam.mutate() : view === "Prezențe" ? addAttendance.mutate() : view === "Taskuri" ? addUniTask.mutate() : view === "Proiecte" ? addUniProject.mutate() : addSubject.mutate()} className="rounded-xl bg-primary px-3 py-2 text-xs text-white">Salvează</button></div>
          </div>}
          <div className="mb-6">
        <p className="text-text-secondary text-sm">{subjects.length} materii · media {avgGrade}</p>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-2">
          {[["Taskuri", overview.open_tasks ?? 0], ["Proiecte", overview.projects_count ?? 0], ["Examene", overview.exams_count ?? 0], ["Prezență", overview.attendance_pct != null ? `${overview.attendance_pct}%` : "—"], ["Media ponderată", overview.weighted_average ?? "—"]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-border-light bg-surface/60 px-3 py-2"><p className="text-[10px] text-text-secondary">{label}</p><p className="text-base font-semibold text-text-primary">{value}</p></div>)}
        </div>
      </div>
      {view === "Overview" && <div className="grid gap-3">
        {subjects.length === 0 ? (
          <Card><p className="text-sm text-text-muted text-center py-8">No subjects</p></Card>
        ) : (
          visibleSubjects.map((s) => (
            <Card key={s.id} className="flex items-center gap-4 py-3 px-4">
              <GraduationCap className="w-5 h-5 text-primary" />
              <div className="flex-1">
                <p className="text-sm font-medium">{s.name}</p>
                {s.professor && <p className="text-xs text-text-secondary">{s.professor}</p>}
              </div>
              {s.credits && <span className="text-xs text-text-secondary">{s.credits} cr</span>}
              {s.attendance_pct != null && (
                <span className="text-xs text-cyan-400">{s.attendance_pct}%</span>
              )}
              {s.grade != null && (
                <span className="text-sm font-semibold text-emerald-400">{s.grade}</span>
              )}
            </Card>
          ))
        )}
      </div>}
      {view === "Materii" && <div className="grid gap-3">{subjects.map((s: any) => <Card key={s.id} className="p-4"><div className="flex items-center gap-3"><GraduationCap className="w-5 h-5 text-primary" /><div className="flex-1"><p className="font-medium">{s.name}</p><p className="text-xs text-text-secondary">{s.professor || "Profesor nespecificat"} · {s.credits ?? "—"} credite</p></div><span className="text-sm font-semibold text-emerald-400">{s.weighted_avg_grade ?? s.avg_grade ?? "—"}</span></div></Card>)}</div>}
      {view === "Note" && <div className="space-y-3">{subjects.flatMap((s: any) => (s.grades ?? []).map((g: any, index: number) => <Card key={`${s.id}-${index}`} className="flex items-center gap-3 p-4"><div className="flex-1"><p className="font-medium">{s.name}</p><p className="text-xs text-text-secondary">{g.assessment_title || g.type || "Evaluare"}{g.weight ? ` · ${g.weight}%` : ""}</p></div><span className="text-lg font-semibold text-text-primary">{g.grade}</span></Card>))}</div>}
      {view === "Prezențe" && <div className="space-y-3">{subjects.map((s: any) => { const total = Number(s.total_logged ?? 0); const attended = Number(s.attended_count ?? 0); const pct = total ? Math.round(attended * 100 / total) : 0; return <Card key={s.id} className="p-4"><div className="flex justify-between mb-2"><span className="font-medium">{s.name}</span><span className="text-sm text-text-secondary">{attended}/{total} · {pct}%</span></div><div className="h-1.5 rounded-full bg-surface overflow-hidden"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} /></div></Card>})}</div>}
      {view === "Examene" && <div className="space-y-3">{(data as any)?.upcoming_exams?.map((exam: any) => <Card key={exam.id} className="flex items-center gap-3 p-4"><div className="flex-1"><p className="font-medium">{exam.subject_name}</p><p className="text-xs text-text-secondary">{exam.exam_type} · {exam.room || "Sala nespecificată"}</p></div><span className="text-sm text-text-primary">{String(exam.exam_date)}</span></Card>)}</div>}
      {view === "Taskuri" && <div className="space-y-2">{((data as any)?.academic_work?.tasks ?? []).map((task: any) => <Card key={task.id} className="flex items-center gap-3 p-3"><div className="flex-1"><p className="text-sm font-medium">{task.title}</p><p className="text-xs text-text-secondary">{task.subject_name}{task.due_date ? ` · ${task.due_date}` : ""}</p></div><span className="text-xs text-text-muted">{task.priority}</span></Card>)}</div>}
      {view === "Proiecte" && <div className="space-y-2">{((data as any)?.academic_work?.projects ?? []).map((project: any) => <Card key={project.id} className="flex items-center gap-3 p-3"><div className="flex-1"><p className="text-sm font-medium">{project.name}</p><p className="text-xs text-text-secondary">{project.subject_name}{project.deadline ? ` · ${project.deadline}` : ""}</p></div><span className="text-xs text-text-muted">{project.progress ?? 0}%</span></Card>)}</div>}
      {view === "Orar" && <div className="space-y-3">
        <div className="flex items-center justify-between"><p className="text-xs text-text-secondary">Săptămâna {scheduleData?.week_type === "even" ? "pară" : "impară"}. Sunt afișate doar cursurile active.</p><button type="button" onClick={() => syncCalendar.mutate()} disabled={syncCalendar.isPending} className="text-xs text-primary">{syncCalendar.isPending ? "Sincronizez…" : "Sincronizează Calendar"}</button></div>
        {["Luni", "Marți", "Miercuri", "Joi", "Vineri"].map((day, dayIndex) => {
          const items = (scheduleData?.items ?? []).filter((item: any) => Number(item.day_of_week) === dayIndex)
          return <Card key={day} className="p-4">
            <div className="mb-3 flex items-center justify-between"><p className="font-medium">{day}</p><span className="text-xs text-text-muted">{items.length} {items.length === 1 ? "activitate" : "activități"}</span></div>
            {items.length === 0 ? <p className="text-xs text-text-muted">Fără cursuri</p> : <div className="space-y-2">{items.map((item: any, index: number) => <div key={`${item.id ?? item.subject_name}-${index}`} className="flex items-center gap-3 rounded-xl border border-border-light bg-surface/50 px-3 py-2"><div className="min-w-[74px] text-xs font-medium text-text-primary"><div className="flex items-center gap-1"><Clock className="h-3.5 w-3.5 text-primary" />{String(item.start_time ?? "").slice(0, 5)}</div><span className="pl-4 text-text-muted">{String(item.end_time ?? "").slice(0, 5)}</span></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{item.subject_name || "Activitate"}</p><p className="text-xs text-text-secondary">{item.class_type || "Curs"}{item.week_type && item.week_type !== "both" ? ` · ${item.week_type === "even" ? "săptămâni pare" : "săptămâni impare"}` : ""}</p></div>{item.room && <span className="flex items-center gap-1 text-xs text-text-secondary"><MapPin className="h-3.5 w-3.5" />{item.room}</span>}<button type="button" onClick={() => editSchedule.mutate(item)} className="text-xs text-text-secondary hover:text-primary">Editează</button><button type="button" onClick={() => deleteSchedule.mutate(Number(item.id))} className="text-xs text-text-muted hover:text-red-400" aria-label="Elimină intrarea">Șterge</button></div>)}</div>}
          </Card>
        })}
      </div>}
        </motion.div>
      </div>
    </div>
  )
}
