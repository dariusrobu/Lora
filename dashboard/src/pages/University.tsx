import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { GraduationCap, Plus, Clock, MapPin, ArrowLeft } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"
import { PageHeader, ModeSelector, DateField } from "../components/ui"
import type { UniversitySubject } from "../types"
import { api } from "../api/client"
import AcademicCalendar from "./daily/AcademicCalendar"

type ApiFetchOptions = { method?: string; headers?: Record<string, string>; body?: string }

// Keep this page on the same authenticated client as the rest of the dashboard.
// Native fetch() bypasses the Telegram JWT interceptor and silently produced 401/empty data.
async function apiFetch(url: string, options: ApiFetchOptions = {}) {
  const response = await api.request({
    url,
    method: options.method ?? "GET",
    headers: options.headers,
    data: options.body ? JSON.parse(options.body) : undefined,
  })
  return { ok: true, json: async () => response.data }
}

export default function University() {
  const [view, setView] = useState("Orar")
  const [manageScheduleOpen, setManageScheduleOpen] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState("")
  const [selectedSubject, setSelectedSubject] = useState<any | null>(null)
  const [editingSubject, setEditingSubject] = useState(false)
  const [editSubjectName, setEditSubjectName] = useState("")
  const [editSubjectProfessor, setEditSubjectProfessor] = useState("")
  const [editSubjectCredits, setEditSubjectCredits] = useState("")
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
  const [attendanceType, setAttendanceType] = useState("curs")
  const [uniTaskSubject, setUniTaskSubject] = useState("")
  const [uniTaskTitle, setUniTaskTitle] = useState("")
  const [uniTaskDue, setUniTaskDue] = useState("")
  const [uniTaskType, setUniTaskType] = useState("curs")
  const [uniTaskDescription, setUniTaskDescription] = useState("")
  const [uniTaskTags, setUniTaskTags] = useState<string[]>([])
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
      const response = await apiFetch("/api/university/subjects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, professor, credits: credits ? Number(credits) : null }) })
      if (!response.ok) throw new Error("Nu am putut adăuga materia")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setName(""); setProfessor(""); setCredits("") },
  })
  const addGrade = useMutation({
    mutationFn: async () => {
      const response = await apiFetch("/api/university/grades", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_id: Number(gradeSubject), grade: Number(gradeValue), grade_type: gradeType, weight: gradeWeight ? Number(gradeWeight) : null }) })
      if (!response.ok) throw new Error("Nu am putut adăuga nota")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setGradeSubject(""); setGradeValue(""); setGradeWeight("") },
  })
  const addExam = useMutation({
    mutationFn: async () => {
      const response = await apiFetch("/api/university/exams", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_id: Number(examSubject), exam_date: examDate, exam_type: examType, room: examRoom || null }) })
      if (!response.ok) throw new Error("Nu am putut adăuga examenul")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setExamSubject(""); setExamDate(""); setExamRoom("") },
  })
  const addAttendance = useMutation({
    mutationFn: async () => {
      const response = await apiFetch("/api/university/attendance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_id: Number(attendanceSubject), class_date: attendanceDate, attended: attendancePresent, class_type: attendanceType }) })
      if (!response.ok) throw new Error("Nu am putut înregistra prezența")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); setShowAdd(false); setAttendanceSubject(""); setAttendanceDate("") },
    onError: (error: any) => window.alert(error?.response?.data?.detail || "Nu am putut înregistra prezența."),
  })
  const addUniTask = useMutation({
    mutationFn: async () => {
      const response = await apiFetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: uniTaskTitle, description: uniTaskDescription || null, tags: uniTaskTags, due_date: uniTaskDue || null, university_subject_id: Number(uniTaskSubject), class_type: uniTaskType }) })
      if (!response.ok) throw new Error("Nu am putut adăuga taskul")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university"] }); qc.invalidateQueries({ queryKey: ["university-tasks"] }); setShowAdd(false); setUniTaskSubject(""); setUniTaskTitle(""); setUniTaskDue(""); setUniTaskDescription(""); setUniTaskTags([]) },
  })
  const addSchedule = useMutation({
    mutationFn: async () => {
      const subject = subjects.find((item: any) => item.name.toLowerCase() === scheduleSubject.trim().toLowerCase())
      if (!subject) throw new Error("Selectează o materie activă")
      const response = await apiFetch("/api/university/schedule", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_id: subject.id, subject_name: subject.name, day_of_week: Number(scheduleDay), start_time: scheduleStart, end_time: scheduleEnd, room: scheduleRoom || null, class_type: scheduleType, week_type: scheduleWeek }) })
      if (!response.ok) throw new Error("Nu am putut adăuga cursul")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university-schedule"] }); qc.invalidateQueries({ queryKey: ["calendar"] }); setShowAdd(false); setScheduleSubject(""); setScheduleRoom("") },
  })
  const deleteSchedule = useMutation({
    mutationFn: async (id: number) => {
      const response = await apiFetch(`/api/university/schedule/${id}`, { method: "DELETE" })
      if (!response.ok) throw new Error("Nu am putut elimina intrarea")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university-schedule"] }); qc.invalidateQueries({ queryKey: ["calendar"] }) },
  })
  const editSchedule = useMutation({
    mutationFn: async (item: any) => {
      const room = window.prompt("Sala:", item.room || "")
      if (room === null) return null
      const start = window.prompt("Ora de început (HH:MM):", String(item.start_time || "").slice(0, 5))
      if (start === null) return null
      const end = window.prompt("Ora de sfârșit (HH:MM):", String(item.end_time || "").slice(0, 5))
      if (end === null) return null
      const response = await apiFetch(`/api/university/schedule/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_name: item.subject_name, day_of_week: item.day_of_week, start_time: start, end_time: end, room: room || null, class_type: item.class_type || "curs", week_type: item.week_type || "both" }) })
      if (!response.ok) throw new Error("Nu am putut modifica intrarea")
      return response.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["university-schedule"] }); qc.invalidateQueries({ queryKey: ["calendar"] }) },
  })
  const syncCalendar = useMutation({
    mutationFn: async () => { const response = await apiFetch("/api/university/calendar-sync", { method: "POST" }); if (!response.ok) throw new Error("Calendar indisponibil"); return response.json() },
  })
  const { data, isLoading } = useQuery<{ subjects: UniversitySubject[] }>({
    queryKey: ["university"],
    queryFn: () => apiFetch("/api/university/summary").then((r) => r.json()),
  })
  const { data: scheduleData } = useQuery<{ week_type?: string; items?: any[] }>({
    queryKey: ["university-schedule"],
    queryFn: () => apiFetch("/api/university/schedule?week_type=all").then((r) => r.json()),
    enabled: view === "Orar" && manageScheduleOpen,
  })
  const { data: tasksData } = useQuery<any[]>({
    queryKey: ["university-tasks"],
    queryFn: () => apiFetch("/api/tasks?status=pending").then((r) => r.json()),
    enabled: view === "Taskuri",
  })
  const updateUniTask = useMutation({
    mutationFn: async (task: any) => {
      const title = window.prompt("Titlu task:", task.title)
      if (title === null || !title.trim()) return
      const description = window.prompt("Descriere:", task.description || "")
      await api.patch(`/api/tasks/${task.id}`, { title: title.trim(), description: description ?? task.description ?? null })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["university-tasks"] }),
    onError: (error: any) => window.alert(error?.response?.data?.detail || "Nu am putut actualiza taskul."),
  })
  const completeUniTask = useMutation({
    mutationFn: async (id: number) => apiFetch(`/api/tasks/${id}/complete`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["university-tasks"] }),
  })
  const deleteUniTask = useMutation({
    mutationFn: async (id: number) => apiFetch(`/api/tasks/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["university-tasks"] }),
  })

  if (isLoading && view !== "Orar") return <Spinner className="py-12" />

  const subjects = data?.subjects ?? []
  const visibleSubjects = subjects.filter((subject: any) => subject.name.toLowerCase().includes(search.toLowerCase()) || String(subject.professor ?? "").toLowerCase().includes(search.toLowerCase()))
  const overview = (data as any)?.overview ?? {}
  const avgGrade = subjects.length
    ? (subjects.reduce((s, x) => s + (x.grade ?? 0), 0) / subjects.length).toFixed(1)
    : "-"

  if (selectedSubject) {
    const subject = selectedSubject
    const grades = subject.grades ?? []
    const openSubjectAction = (target: string) => {
      setSelectedSubject(null)
      setView(target)
      setShowAdd(true)
      if (target === "Note") setGradeSubject(String(subject.id))
      if (target === "Examene") setExamSubject(String(subject.id))
      if (target === "Prezențe") { setAttendanceSubject(String(subject.id)); setAttendanceDate(new Date().toISOString().slice(0, 10)); setAttendanceType("curs") }
      if (target === "Taskuri") setUniTaskSubject(String(subject.id))
    }
    const editSubject = () => {
      setEditSubjectName(subject.name)
      setEditSubjectProfessor(subject.professor || "")
      setEditSubjectCredits(String(subject.credits ?? ""))
      setEditingSubject(true)
    }
    const saveSubject = async () => {
      if (!editSubjectName.trim()) return
      await api.put(`/api/university/subjects/${subject.id}`, { name: editSubjectName.trim(), professor: editSubjectProfessor.trim() || null, credits: editSubjectCredits ? Number(editSubjectCredits) : null })
      await qc.invalidateQueries({ queryKey: ["university"] })
      setEditingSubject(false)
      setSelectedSubject(null)
    }
    const removeSubject = async () => {
      if (!window.confirm(`Dezactivezi materia „${subject.name}”? Istoricul rămâne păstrat.`)) return
      await api.delete(`/api/university/subjects/${subject.id}`)
      await qc.invalidateQueries({ queryKey: ["university"] })
      setSelectedSubject(null)
    }
    const removeAcademicItem = async (kind: "grades" | "attendance" | "exams", id: number) => {
      if (!window.confirm("Ștergi această înregistrare?")) return
      await api.delete(`/api/university/${kind === "grades" ? "grades" : kind === "exams" ? "exams" : "attendance"}/${id}`)
      await qc.invalidateQueries({ queryKey: ["university"] })
      setSelectedSubject(null)
    }
    return (
      <div className="card-liquid-page">
        <div className="card-liquid-page-content p-4 sm:p-6">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <button type="button" onClick={() => setSelectedSubject(null)} className="mb-5 flex items-center gap-2 text-sm text-text-secondary hover:text-primary"><ArrowLeft className="h-4 w-4" /> Înapoi la materii</button>
            <div className="mb-6 flex items-start gap-3"><GraduationCap className="mt-1 h-7 w-7 text-primary" /><div><h1 className="text-xl font-semibold text-text-primary">{subject.name}</h1><p className="text-sm text-text-secondary">{subject.professor || "Profesor nespecificat"} · {subject.credits ?? "—"} credite</p></div></div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[["Medie", subject.weighted_avg_grade ?? subject.avg_grade ?? "—"], ["Prezență", `${subject.attended_count ?? 0}/${subject.total_logged ?? 0}`], ["Examene", subject.upcoming_exam_count ?? 0], ["Taskuri", subject.open_task_count ?? 0]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-border-light bg-surface/60 px-3 py-2"><p className="text-[10px] text-text-secondary">{label}</p><p className="text-base font-semibold text-text-primary">{value}</p></div>)}
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {[['Prezență', 'Prezențe'], ['Notă / test', 'Note'], ['Examen', 'Examene'], ['Task', 'Taskuri']].map(([label, target]) => <button key={target} type="button" onClick={() => openSubjectAction(target)} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary transition-colors hover:border-primary hover:text-primary">+ {label}</button>)}
            </div>
            {editingSubject && <div className="mt-4 grid gap-2 rounded-xl border border-border-light bg-surface/50 p-3 sm:grid-cols-3"><input value={editSubjectName} onChange={(e) => setEditSubjectName(e.target.value)} placeholder="Nume materie" className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm" /><input value={editSubjectProfessor} onChange={(e) => setEditSubjectProfessor(e.target.value)} placeholder="Profesor" className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm" /><input value={editSubjectCredits} onChange={(e) => setEditSubjectCredits(e.target.value)} placeholder="Credite" type="number" className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm" /><div className="flex gap-2 sm:col-span-3"><button type="button" onClick={() => setEditingSubject(false)} className="rounded-lg border border-border px-3 py-2 text-xs text-text-secondary">Anulează</button><button type="button" onClick={saveSubject} disabled={!editSubjectName.trim()} className="rounded-lg bg-primary px-3 py-2 text-xs text-white">Salvează</button></div></div>}
            <div className="mt-4 flex gap-2 border-t border-border-light pt-4"><button type="button" onClick={editSubject} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary hover:border-primary hover:text-primary">Editează materia</button><button type="button" onClick={removeSubject} className="rounded-xl border border-red-300/30 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10">Dezactivează materia</button></div>
            <section className="mt-6"><h2 className="mb-2 text-sm font-semibold text-text-primary">Note și teste</h2>{grades.length ? <div className="space-y-2">{grades.map((grade: any) => <Card key={grade.id} className="flex items-center gap-3 p-3"><span className="flex-1 text-sm text-text-secondary">{grade.assessment_title || grade.grade_type || "Evaluare"}</span><span className="font-semibold text-text-primary">{grade.grade}</span><button type="button" onClick={() => removeAcademicItem("grades", grade.id)} className="text-xs text-red-400">Șterge</button></Card>)}</div> : <p className="text-sm text-text-muted">Nu există note înregistrate.</p>}</section>
            <section className="mt-6"><h2 className="mb-3 text-sm font-semibold text-text-primary">Prezențe</h2>{(subject.attendance_by_type ?? []).length ? <div className="mb-4 grid gap-3 sm:grid-cols-2">{["curs", "seminar"].map((type) => { const stat = (subject.attendance_by_type ?? []).find((item: any) => item.class_type === type) ?? { total: 0, attended: 0, absent: 0 }; return <Card key={type} className="p-3"><div className="mb-2 flex items-center justify-between"><span className="font-medium">{type === "curs" ? "Curs" : "Seminar"}</span><span className="text-xs text-text-secondary">{stat.attended}/{stat.total} prezente</span></div><div className="flex gap-3 text-xs"><span className="text-emerald-500">Prezente: {stat.attended}</span><span className="text-red-400">Absențe: {stat.absent}</span></div></Card> })}</div> : <p className="mb-4 text-sm text-text-muted">Nu există prezențe înregistrate.</p>}{(subject.attendance_rows ?? []).map((row: any) => <Card key={row.id} className="flex items-center gap-3 p-3"><span className="flex-1 text-sm text-text-secondary">{String(row.class_date)} · {row.class_type === "seminar" ? "Seminar" : "Curs"}</span><span className={row.attended ? "text-emerald-500" : "text-red-400"}>{row.attended ? "Prezent" : "Absent"}</span><button type="button" onClick={() => removeAcademicItem("attendance", row.id)} className="text-xs text-red-400">Șterge</button></Card>)}</section>
            <section className="mt-6"><h2 className="mb-2 text-sm font-semibold text-text-primary">Examene</h2>{(subject.upcoming_exams ?? []).length ? <div className="space-y-2">{subject.upcoming_exams.map((exam: any) => <Card key={exam.id} className="flex items-center gap-3 p-3"><span className="flex-1 text-sm text-text-secondary">{String(exam.exam_date)} · {exam.exam_type}</span><span className="text-xs text-text-muted">{exam.room || "Fără sală"}</span><button type="button" onClick={() => removeAcademicItem("exams", exam.id)} className="text-xs text-red-400">Șterge</button></Card>)}</div> : <p className="text-sm text-text-muted">Nu există examene viitoare.</p>}</section>
          </motion.div>
        </div>
      </div>
    )
  }

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-4 sm:p-6">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <PageHeader eyebrow="Facultate" title={view === "Overview" ? "Facultate" : view} description="Programul tău academic, zi cu zi." action={<div className="flex items-center gap-2"><ModeSelector value={view} options={["Orar", "Materii", "Taskuri", "Note", "Prezențe", "Examene", "Overview"].map((item) => ({ value: item, label: item }))} onChange={(next) => { setView(next); setShowAdd(false) }} /><button type="button" onClick={() => setShowAdd((v) => !v)} className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white" aria-label="Adaugă la facultate"><Plus className="h-4 w-4" /></button></div>} />
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
            {view === "Examene" && <div className="grid gap-2 sm:grid-cols-4"><select value={examSubject} onChange={(e) => setExamSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><DateField value={examDate} onChange={(e) => setExamDate(e.target.value)} aria-label="Data examen" className="h-10 px-3 py-2 text-sm" /><select value={examType} onChange={(e) => setExamType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="final">Examen</option><option value="partial">Test</option><option value="colocviu">Colocviu</option></select><input value={examRoom} onChange={(e) => setExamRoom(e.target.value)} placeholder="Sală" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div>}
            {view === "Prezențe" && <div className="grid gap-2 sm:grid-cols-4"><select value={attendanceSubject} onChange={(e) => setAttendanceSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><DateField value={attendanceDate} onChange={(e) => setAttendanceDate(e.target.value)} aria-label="Data prezență" className="h-10 px-3 py-2 text-sm" /><select value={attendanceType} onChange={(e) => setAttendanceType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="curs">Curs</option><option value="seminar">Seminar</option></select><select value={attendancePresent ? "present" : "absent"} onChange={(e) => setAttendancePresent(e.target.value === "present")} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="present">Prezent</option><option value="absent">Absent</option></select></div>}
            {view === "Taskuri" && <div className="space-y-3"><div className="grid gap-2 sm:grid-cols-2"><input autoFocus value={uniTaskTitle} onChange={(e) => setUniTaskTitle(e.target.value)} placeholder="Titlul taskului" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><select value={uniTaskSubject} onChange={(e) => setUniTaskSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><select value={uniTaskType} onChange={(e) => setUniTaskType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="curs">Curs</option><option value="seminar">Seminar</option></select><DateField value={uniTaskDue} onChange={(e) => setUniTaskDue(e.target.value)} label="Termen" /></div><textarea value={uniTaskDescription} onChange={(e) => setUniTaskDescription(e.target.value)} placeholder="Descriere sau pași de lucru (opțional)" rows={3} className="w-full resize-y rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><div><p className="mb-1 text-xs text-text-muted">Etichete</p><div className="flex flex-wrap gap-2">{["Homework", "Study", "Project", "Reading"].map((tag) => <button type="button" key={tag} onClick={() => setUniTaskTags((current) => current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag])} className={`rounded-full border px-3 py-1 text-xs ${uniTaskTags.includes(tag) ? "border-primary bg-primary/10 text-primary" : "border-border text-text-secondary"}`}>{tag}</button>)}</div></div></div>}
            <div className="mt-3 flex gap-2"><button type="button" onClick={() => setShowAdd(false)} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary">Anulează</button><button type="button" onClick={() => view === "Note" ? addGrade.mutate() : view === "Examene" ? addExam.mutate() : view === "Prezențe" ? addAttendance.mutate() : view === "Taskuri" ? addUniTask.mutate() : addSubject.mutate()} className="rounded-xl bg-primary px-3 py-2 text-xs text-white">Salvează</button></div>
          </div>}
          {view !== "Orar" && <div className="mb-6">
        <p className="text-text-secondary text-sm">{subjects.length} materii · media {avgGrade}</p>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-2">
          {[["Taskuri", overview.open_tasks ?? 0], ["Proiecte", overview.projects_count ?? 0], ["Examene", overview.exams_count ?? 0], ["Prezență", overview.attendance_pct != null ? `${overview.attendance_pct}%` : "—"], ["Media ponderată", overview.weighted_average ?? "—"]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-border-light bg-surface/60 px-3 py-2"><p className="text-[10px] text-text-secondary">{label}</p><p className="text-base font-semibold text-text-primary">{value}</p></div>)}
        </div>
      </div>}
      {view === "Overview" && <div className="grid gap-3">
        {subjects.length === 0 ? (
          <Card><p className="text-sm text-text-muted text-center py-8">No subjects</p></Card>
        ) : (
          visibleSubjects.map((s) => (
            <Card key={s.id} onClick={() => setSelectedSubject(s)} className="flex cursor-pointer items-center gap-4 py-3 px-4 transition-colors hover:border-primary/50">
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
      {view === "Materii" && <div className="grid gap-3">{subjects.map((s: any) => <Card key={s.id} onClick={() => setSelectedSubject(s)} className="cursor-pointer p-4 transition-colors hover:border-primary/50"><div className="flex items-center gap-3"><GraduationCap className="w-5 h-5 text-primary" /><div className="flex-1"><p className="font-medium">{s.name}</p><p className="text-xs text-text-secondary">{s.professor || "Profesor nespecificat"} · {s.credits ?? "—"} credite</p></div><span className="text-sm font-semibold text-emerald-400">{s.weighted_avg_grade ?? s.avg_grade ?? "—"}</span></div></Card>)}</div>}
      {view === "Note" && <div className="space-y-3">{subjects.flatMap((s: any) => (s.grades ?? []).map((g: any, index: number) => <Card key={`${s.id}-${index}`} className="flex items-center gap-3 p-4"><div className="flex-1"><p className="font-medium">{s.name}</p><p className="text-xs text-text-secondary">{g.assessment_title || g.type || "Evaluare"}{g.weight ? ` · ${g.weight}%` : ""}</p></div><span className="text-lg font-semibold text-text-primary">{g.grade}</span></Card>))}</div>}
      {view === "Prezențe" && <div className="space-y-3">{subjects.map((s: any) => { const total = Number(s.total_logged ?? 0); const attended = Number(s.attended_count ?? 0); const pct = total ? Math.round(attended * 100 / total) : 0; return <Card key={s.id} className="p-4"><div className="flex justify-between mb-2"><span className="font-medium">{s.name}</span><span className="text-sm text-text-secondary">{attended}/{total} · {pct}%</span></div><div className="h-1.5 rounded-full bg-surface overflow-hidden"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} /></div></Card>})}</div>}
      {view === "Examene" && <div className="space-y-3">{(data as any)?.upcoming_exams?.map((exam: any) => <Card key={exam.id} className="flex items-center gap-3 p-4"><div className="flex-1"><p className="font-medium">{exam.subject_name}</p><p className="text-xs text-text-secondary">{exam.exam_type} · {exam.room || "Sala nespecificată"}</p></div><span className="text-sm text-text-primary">{String(exam.exam_date)}</span></Card>)}</div>}
      {view === "Taskuri" && <div className="space-y-4">{(!tasksData?.filter((task: any) => task.university_subject_id).length) && <p className="text-sm text-text-muted">Nu există taskuri universitare active.</p>}{subjects.map((subject: any) => { const tasks = (tasksData ?? []).filter((task: any) => Number(task.university_subject_id) === Number(subject.id)); if (!tasks.length) return null; return <section key={subject.id}><h2 className="mb-2 text-sm font-semibold text-text-primary">{subject.name}</h2>{["curs", "seminar"].map((type) => { const grouped = tasks.filter((task: any) => (task.class_type || "curs") === type); if (!grouped.length) return null; return <div key={type} className="mb-3"><p className="mb-1 text-xs text-text-muted">{type === "curs" ? "Curs" : "Seminar"}</p>{grouped.map((task: any) => <Card key={task.id} className="p-3"><div className="flex items-center gap-3"><div className="flex-1"><p className="text-sm font-medium">{task.title}</p><p className="text-xs text-text-secondary">{task.due_date ? `Termen: ${task.due_date}` : "Fără termen"}</p></div><span className="text-xs text-text-muted">{task.priority}</span></div><div className="mt-2 flex gap-2"><button type="button" onClick={() => updateUniTask.mutate(task)} className="text-xs text-text-secondary hover:text-primary">Editează</button><button type="button" onClick={() => completeUniTask.mutate(Number(task.id))} className="text-xs text-emerald-500">Completează</button><button type="button" onClick={() => { if (window.confirm("Ștergi taskul?")) deleteUniTask.mutate(Number(task.id)) }} className="text-xs text-red-400">Șterge</button></div>{task.description && <p className="mt-2 text-xs text-text-secondary">{task.description}</p>}{task.tags?.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{task.tags.map((tag: string) => <span key={tag} className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary">{tag}</span>)}</div>}</Card>)}</div>})}</section> })}</div>}
      {view === "Orar" && <div className="space-y-3">
        <AcademicCalendar />
        <details className="rounded-2xl border border-border-light bg-surface/60 p-4" onToggle={(event) => setManageScheduleOpen(event.currentTarget.open)}>
          <summary className="cursor-pointer text-sm font-medium text-text-primary">Gestionează orarul recurent</summary>
          <div className="mt-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="min-w-0 text-xs text-text-secondary">Sunt afișate cursurile active din săptămânile pare și impare.</p><button type="button" onClick={() => syncCalendar.mutate()} disabled={syncCalendar.isPending} className="shrink-0 text-xs text-primary">{syncCalendar.isPending ? "Sincronizez…" : "Sincronizează Calendar"}</button></div>
        {["Luni", "Marți", "Miercuri", "Joi", "Vineri"].map((day, dayIndex) => {
          const items = (scheduleData?.items ?? []).filter((item: any) => Number(item.day_of_week) === dayIndex)
          return <Card key={day} className="p-4">
            <div className="mb-3 flex items-center justify-between"><p className="font-medium">{day}</p><span className="text-xs text-text-muted">{items.length} {items.length === 1 ? "activitate" : "activități"}</span></div>
            {items.length === 0 ? <p className="text-xs text-text-muted">Fără cursuri</p> : <div className="space-y-2">{items.map((item: any, index: number) => <div key={`${item.id ?? item.subject_name}-${index}`} className="flex flex-wrap items-center gap-3 rounded-xl border border-border-light bg-surface/50 px-3 py-2"><div className="min-w-[74px] text-xs font-medium text-text-primary"><div className="flex items-center gap-1"><Clock className="h-3.5 w-3.5 text-primary" />{String(item.start_time ?? "").slice(0, 5)}</div><span className="pl-4 text-text-muted">{String(item.end_time ?? "").slice(0, 5)}</span></div><div className="min-w-[110px] flex-1"><p className="break-words text-sm font-medium">{item.subject_name || "Activitate"}</p><p className="text-xs text-text-secondary">{item.class_type || "Curs"}{item.week_type && item.week_type !== "both" ? ` · ${item.week_type === "even" ? "săptămână pară" : "săptămână impară"}` : " · ambele săptămâni"}</p></div>{item.room && <span className="flex items-center gap-1 text-xs text-text-secondary"><MapPin className="h-3.5 w-3.5" />{item.room}</span>}<button type="button" onClick={() => editSchedule.mutate(item)} className="text-xs text-text-secondary hover:text-primary">Editează</button><button type="button" onClick={() => deleteSchedule.mutate(Number(item.id))} className="text-xs text-text-muted hover:text-red-400" aria-label="Elimină intrarea">Șterge</button></div>)}</div>}
          </Card>
        })}
          </div>
        </details>
      </div>}
        </motion.div>
      </div>
    </div>
  )
}
