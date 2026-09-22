import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { GraduationCap, ChevronDown, Plus } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"
import type { UniversitySubject } from "../types"

export default function University() {
  const [view, setView] = useState("Overview")
  const [showAdd, setShowAdd] = useState(false)
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
  const { data, isLoading } = useQuery<{ subjects: UniversitySubject[] }>({
    queryKey: ["university"],
    queryFn: () => fetch("/api/university/summary").then((r) => r.json()),
  })

  if (isLoading) return <Spinner className="py-12" />

  const subjects = data?.subjects ?? []
  const overview = (data as any)?.overview ?? {}
  const avgGrade = subjects.length
    ? (subjects.reduce((s, x) => s + (x.grade ?? 0), 0) / subjects.length).toFixed(1)
    : "-"

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="mb-6 flex items-center justify-between"><label className="relative flex w-fit items-center gap-2 text-sm font-semibold text-text-primary"><span>University · {view}</span><ChevronDown className="w-4 h-4 text-text-muted" /><select value={view} onChange={(e) => setView(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Alege secțiunea University">{["Overview", "Materii", "Note", "Prezențe", "Examene", "Orar"].map((item) => <option key={item}>{item}</option>)}</select></label><button type="button" onClick={() => setShowAdd((v) => !v)} className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-white" aria-label="Adaugă în University"><Plus className="w-4 h-4" /></button></div>
          {showAdd && <div className="mb-6 rounded-2xl border border-border bg-surface/70 p-4"><h2 className="mb-3 text-sm font-semibold">{view === "Note" ? "Adaugă notă" : view === "Examene" ? "Adaugă examen" : "Adaugă materie"}</h2>{view === "Examene" ? <><div className="grid gap-2 sm:grid-cols-4"><select value={examSubject} onChange={(e) => setExamSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><input value={examDate} onChange={(e) => setExamDate(e.target.value)} type="date" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><select value={examType} onChange={(e) => setExamType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="final">Examen</option><option value="partial">Test</option><option value="colocviu">Colocviu</option><option value="restanta">Restanță</option></select><input value={examRoom} onChange={(e) => setExamRoom(e.target.value)} placeholder="Sală" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div><div className="mt-3 flex gap-2"><button type="button" onClick={() => setShowAdd(false)} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary">Anulează</button><button type="button" onClick={() => addExam.mutate()} disabled={!examSubject || !examDate || addExam.isPending} className="rounded-xl bg-primary px-3 py-2 text-xs text-white">Adaugă examen</button></div></> : view === "Note" ? <><div className="grid gap-2 sm:grid-cols-4"><select value={gradeSubject} onChange={(e) => setGradeSubject(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="">Alege materia</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><input value={gradeValue} onChange={(e) => setGradeValue(e.target.value)} placeholder="Nota" type="number" min="1" max="10" step="0.01" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><select value={gradeType} onChange={(e) => setGradeType(e.target.value)} className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm"><option value="exam">Examen</option><option value="partial">Test</option><option value="proiect">Proiect</option><option value="laborator">Laborator</option></select><input value={gradeWeight} onChange={(e) => setGradeWeight(e.target.value)} placeholder="Pondere %" type="number" min="0" max="100" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div><div className="mt-3 flex gap-2"><button type="button" onClick={() => setShowAdd(false)} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary">Anulează</button><button type="button" onClick={() => addGrade.mutate()} disabled={!gradeSubject || !gradeValue || addGrade.isPending} className="rounded-xl bg-primary px-3 py-2 text-xs text-white">Adaugă nota</button></div></> : <><div className="grid gap-2 sm:grid-cols-3"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nume materie" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><input value={professor} onChange={(e) => setProfessor(e.target.value)} placeholder="Profesor" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /><input value={credits} onChange={(e) => setCredits(e.target.value)} placeholder="Credite" type="number" className="rounded-xl border border-border bg-transparent px-3 py-2 text-sm" /></div><div className="mt-3 flex gap-2"><button type="button" onClick={() => setShowAdd(false)} className="rounded-xl border border-border px-3 py-2 text-xs text-text-secondary">Anulează</button><button type="button" onClick={() => addSubject.mutate()} disabled={!name.trim() || addSubject.isPending} className="rounded-xl bg-primary px-3 py-2 text-xs text-white">Adaugă</button></div></>}</div>}
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
          subjects.map((s) => (
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
      {view === "Orar" && <Card><p className="text-sm text-text-secondary">Orarul complet este disponibil în Calendar și se sincronizează automat cu programul universitar.</p></Card>}
        </motion.div>
      </div>
    </div>
  )
}
