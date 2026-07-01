import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { GraduationCap, User, Hash, Trophy, Percent } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"
import type { UniversitySubject } from "../types"

export default function University() {
  const { data, isLoading } = useQuery<{ subjects: UniversitySubject[] }>({
    queryKey: ["university"],
    queryFn: () => fetch("/api/university/summary").then((r) => r.json()),
  })

  if (isLoading) return <Spinner className="py-12" />

  const subjects = data?.subjects ?? []
  const avgGrade = subjects.length
    ? (subjects.reduce((s, x) => s + (x.grade ?? 0), 0) / subjects.length).toFixed(1)
    : "-"

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="mb-6">
        <h1 className="text-2xl font-bold">University</h1>
        <p className="text-text-secondary text-sm">{subjects.length} subjects, avg grade {avgGrade}</p>
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
