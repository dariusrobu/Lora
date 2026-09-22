import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { GraduationCap, ChevronDown } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"
import type { UniversitySubject } from "../types"

export default function University() {
  const [view, setView] = useState("Overview")
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
          <label className="relative mb-6 flex w-fit items-center gap-2 text-sm font-semibold text-text-primary"><span>University · {view}</span><ChevronDown className="w-4 h-4 text-text-muted" /><select value={view} onChange={(e) => setView(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Alege secțiunea University">{["Overview", "Materii", "Note", "Prezențe", "Examene", "Orar"].map((item) => <option key={item}>{item}</option>)}</select></label>
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
