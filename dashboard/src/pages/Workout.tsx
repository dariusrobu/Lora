import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { Dumbbell, Clock, CalendarDays, TrendingUp, ChevronDown, ChevronUp, Plus } from "lucide-react"
import { Card, Button, Spinner } from "../components/ui"
import { fetchWorkoutStats, logWorkout } from "../api/queries/workout"
import type { WorkoutSession } from "../types"

const sportOptions = [
  "Gym", "Alergare", "Ciclism", "HIIT", "Yoga", "Fotbal", "Baschet",
  "Stretching", "Powerlifting", "Calisthenics", "Padel", "Tenis",
]

function fmtDate(d: string) {
  const dt = new Date(d + "T00:00:00")
  return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function SportIcon({ type }: { type?: string }) {
  const iconMap: Record<string, string> = {
    Gym: "🏋️", Alergare: "🏃", Ciclism: "🚴", HIIT: "🤸",
    Yoga: "🧘", Fotbal: "⚽", Baschet: "🏀", Stretching: "🤸",
    Powerlifting: "🏋️", Calisthenics: "💪", Padel: "🎾", Tenis: "🎾",
  }
  return <span className="text-sm">{iconMap[type ?? ""] ?? "🏋️"}</span>
}

export default function Workout() {
  const [sport, setSport] = useState("Gym")
  const [duration, setDuration] = useState("")
  const [calories, setCalories] = useState("")
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["workout"],
    queryFn: fetchWorkoutStats,
  })

  const logMut = useMutation({
    mutationFn: logWorkout,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workout"] })
      setDuration("")
      setCalories("")
    },
  })

  const handleLog = () => {
    logMut.mutate({
      sport_name: sport,
      duration_min: Number(duration),
      calories: calories ? Number(calories) : undefined,
    })
  }

  if (isLoading) return <Spinner className="py-12" />

  const { stats, recent, personal_records } = data ?? {
    stats: { total_sessions: 0, active_days: 0, most_common_type: null, avg_duration: null },
    recent: [] as WorkoutSession[],
    personal_records: [],
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Workout</h1>
        <p className="text-text-secondary text-sm">Track your training sessions</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-strong rounded-2xl p-4 shadow-apple-heavy">
          <div className="flex items-center gap-2 mb-1.5">
            <Dumbbell className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-apple-caption2 text-text-muted">Sessions</span>
          </div>
          <p className="text-2xl font-bold text-text-primary">{stats.total_sessions}</p>
          <p className="text-apple-caption2 text-text-muted">last 30 days</p>
        </div>
        <div className="glass-strong rounded-2xl p-4 shadow-apple-heavy">
          <div className="flex items-center gap-2 mb-1.5">
            <Clock className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-apple-caption2 text-text-muted">Avg Duration</span>
          </div>
          <p className="text-2xl font-bold text-text-primary">{stats.avg_duration ?? "-"}</p>
          <p className="text-apple-caption2 text-text-muted">minutes</p>
        </div>
        <div className="glass-strong rounded-2xl p-4 shadow-apple-heavy">
          <div className="flex items-center gap-2 mb-1.5">
            <CalendarDays className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-apple-caption2 text-text-muted">Active Days</span>
          </div>
          <p className="text-2xl font-bold text-text-primary">{stats.active_days}</p>
          <p className="text-apple-caption2 text-text-muted">days</p>
        </div>
        <div className="glass-strong rounded-2xl p-4 shadow-apple-heavy">
          <div className="flex items-center gap-2 mb-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-apple-caption2 text-text-muted">Most Often</span>
          </div>
          <p className="text-2xl font-bold flex items-center gap-1">
            <SportIcon type={stats.most_common_type ?? undefined} />
            <span className="text-sm text-text-primary">{stats.most_common_type ?? "-"}</span>
          </p>
          <p className="text-apple-caption2 text-text-muted">sport type</p>
        </div>
      </div>

      {/* Quick Log */}
      <div className="glass-strong rounded-2xl p-4 shadow-apple-heavy">
        <p className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider mb-3">Quick Log</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
          <select
            value={sport}
            onChange={(e) => setSport(e.target.value)}
            className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary outline-none focus:border-primary/30 transition-colors"
          >
            {sportOptions.map((s) => (
              <option key={s} value={s} className="bg-bg">{s}</option>
            ))}
          </select>
          <input
            placeholder="Duration (min)"
            type="number"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
          />
          <input
            placeholder="Calories (optional)"
            type="number"
            value={calories}
            onChange={(e) => setCalories(e.target.value)}
            className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
          />
        </div>
        <Button
          onClick={handleLog}
          disabled={logMut.isPending || !duration.trim()}
          className="w-full sm:w-auto"
        >
          {logMut.isPending ? <Spinner size="sm" /> : "Log"}
        </Button>
      </div>

      {/* Personal Records */}
      {personal_records.length > 0 && (
        <div className="glass-strong rounded-2xl shadow-apple-heavy overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50">
            <h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Personal Records</h4>
          </div>
          <div className="flex flex-wrap gap-2 px-4 py-3">
            {personal_records.map((pr) => (
              <span
                key={pr.exercise_name}
                className="text-xs bg-white/40 dark:bg-white/[0.06] rounded-lg px-2.5 py-1.5 text-text-primary font-medium"
              >
                {pr.exercise_name}: <span className="text-text-primary">{pr.max_weight}kg</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recent Sessions */}
      {recent.length > 0 && (
        <div className="glass-strong rounded-2xl shadow-apple-heavy overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50">
            <h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Last {recent.length} Sessions</h4>
          </div>
          <div className="divide-y divide-border/20">
            {recent.map((session) => (
              <div key={session.id}>
                <button
                  onClick={() => setExpandedId(expandedId === session.id ? null : session.id)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/10 dark:hover:bg-white/[0.04] transition-colors text-left"
                >
                  <span className="text-apple-caption2 text-text-muted w-10 shrink-0 tabular-nums">{fmtDate(session.workout_date)}</span>
                  <span className="text-base shrink-0"><SportIcon type={session.type} /></span>
                  <span className="text-sm font-medium text-text-primary w-16 shrink-0">{session.type}</span>
                  <span className="text-apple-caption2 text-text-secondary w-12 shrink-0 tabular-nums">{session.duration_min}m</span>
                  <span className="text-apple-caption2 text-text-muted w-16 shrink-0">{session.calories ? `${session.calories}cal` : ""}</span>
                  <span className="text-apple-caption2 text-text-muted flex-1">
                    {session.exercises && session.exercises.length > 0
                      ? `${session.exercises.length} ex`
                      : ""}
                  </span>
                  {session.exercises && session.exercises.length > 0 && (
                    <span className="text-text-muted">
                      {expandedId === session.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </span>
                  )}
                </button>
                <AnimatePresence>
                  {expandedId === session.id && session.exercises && session.exercises.length > 0 && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pb-2 px-4 ml-14 space-y-0.5">
                        {session.exercises.map((ex, i) => (
                          <div key={i} className="text-xs text-text-secondary flex items-center gap-2 py-0.5">
                            <span className="text-text-primary font-medium w-28">{ex.name}</span>
                            {ex.weight_kg != null && <span className="text-text-secondary">{ex.weight_kg}kg</span>}
                            {ex.sets != null && <span>× {ex.sets} sets</span>}
                            {ex.reps != null && <span>× {ex.reps} reps</span>}
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}
