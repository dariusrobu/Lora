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
      <div className="grid gap-3">
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
      </div>
        </motion.div>
      </div>
    </div>
  )
}
