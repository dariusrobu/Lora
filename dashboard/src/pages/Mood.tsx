import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { Trash2 } from "lucide-react"
import { Card, Spinner } from "../components/ui"
import type { MoodEntry } from "../types"
import { fetchMoodMonthly, fetchMoodWeekly, logMood, deleteMood } from "../api/queries/mood"
import { MOOD_EMOJI, MOOD_SCORE, MOODS } from "../api/constants/mood"

function fmtDate(d: string) {
  const dt = new Date(d + "T00:00:00")
  return dt.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
}

function getMonthGrid(year: number, month: number) {
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)
  const startDay = first.getDay()
  const days: (number | null)[] = []
  for (let i = 0; i < startDay; i++) days.push(null)
  for (let d = 1; d <= last.getDate(); d++) days.push(d)
  return days
}

export default function Mood() {
  const [period, setPeriod] = useState<"weekly" | "monthly">("weekly")
  const [editingDate, setEditingDate] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const queryFn = period === "weekly" ? fetchMoodWeekly : fetchMoodMonthly
  const { data: entries, isLoading } = useQuery<MoodEntry[]>({
    queryKey: ["mood", period],
    queryFn,
  })

  const logMutation = useMutation({
    mutationFn: logMood,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mood"] })
      setEditingDate(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteMood,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mood"] })
    },
  })

  const stats = useMemo(() => {
    if (!entries || entries.length === 0) return null
    const scores = entries.map((e) => MOOD_SCORE[e.mood] ?? 3).filter(Boolean)
    const avg = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0
    const counts: Record<string, number> = {}
    entries.forEach((e) => { counts[e.mood] = (counts[e.mood] || 0) + 1 })
    const most = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
    return { avg, most: most?.[0] ?? "okay", mostCount: most?.[1] ?? 0, total: entries.length }
  }, [entries])

  const now = new Date()
  const monthDays = getMonthGrid(now.getFullYear(), now.getMonth())
  const dateToEntry = useMemo(() => {
    const map: Record<string, MoodEntry> = {}
    entries?.forEach((e) => { if (e.date) map[e.date] = e })
    return map
  }, [entries])

  if (isLoading) return <Spinner className="py-12" />

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Mood Tracker</h1>
        <p className="text-text-secondary text-sm">How are you feeling?</p>
      </div>

      {/* Mood buttons */}
      <Card className="p-4">
        <div className="flex justify-between">
          {MOODS.map((m) => (
            <button
              key={m}
              onClick={() => logMutation.mutate({ mood: m })}
              disabled={logMutation.isPending}
              className="flex flex-col items-center gap-1 group"
            >
              <span className="text-2xl transition-all group-hover:scale-125 group-hover:drop-shadow-[0_0_8px_rgba(255,255,255,0.15)]">
                {MOOD_EMOJI[m]}
              </span>
              <span className="text-[10px] text-text-muted capitalize group-hover:text-text-secondary transition-colors">{m}</span>
            </button>
          ))}
        </div>
      </Card>

      {/* Summary */}
      {stats && period === "weekly" && (
        <Card className="p-3 flex items-center gap-4">
          <span className="text-2xl">{MOOD_EMOJI[stats.most]}</span>
          <div className="text-xs space-y-0.5">
            <p className="text-text-primary font-medium">Mostly <span className="capitalize">{stats.most}</span> this week</p>
            <p className="text-text-muted">Avg {stats.avg.toFixed(1)} / 5 · {stats.total} of 7 days logged</p>
          </div>
        </Card>
      )}

      {/* Period toggle */}
      <div className="flex gap-2">
        {(["weekly", "monthly"] as const).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              period === p
                ? "bg-surface text-text-primary border border-border"
                : "text-text-secondary border border-transparent hover:text-text-primary"
            }`}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      {period === "weekly" && (
        <div className="space-y-1">
          {entries?.map((entry, i) => (
            <motion.div
              key={entry.date ?? i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className="relative"
            >
              <Card className="flex items-center gap-3 py-2.5 px-3 cursor-pointer" hover onClick={() => entry.date && setEditingDate(editingDate === entry.date ? null : entry.date)}>
                <span className="text-lg">{MOOD_EMOJI[entry.mood] ?? "😐"}</span>
                <span className="text-xs text-text-muted flex-1">{entry.date ? fmtDate(entry.date) : ""}</span>
                <span className="text-xs text-text-primary capitalize font-medium">{entry.mood}</span>
                {entry.date && (
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(entry.date!) }}
                    disabled={deleteMutation.isPending}
                    className="p-1 rounded text-text-muted hover:text-red-400 hover:bg-white/5 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </Card>
              <AnimatePresence>
                {editingDate === entry.date && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="flex justify-between gap-2 px-3 pb-3 pt-1">
                      {MOODS.map((m) => (
                        <button
                          key={m}
                          onClick={() => logMutation.mutate({ mood: m, date: entry.date })}
                          disabled={logMutation.isPending}
                          className="flex flex-col items-center gap-1 p-2 rounded-lg bg-surface border border-border hover:border-text-muted/30 transition-all flex-1"
                        >
                          <span className="text-lg">{MOOD_EMOJI[m]}</span>
                          <span className="text-[9px] text-text-muted capitalize">{m}</span>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      )}

      {period === "monthly" && (
        <Card className="p-3">
          <p className="text-[10px] text-text-muted uppercase tracking-wider mb-3">
            {now.toLocaleDateString("en-US", { month: "long", year: "numeric" })}
          </p>
          <div className="grid grid-cols-7 gap-1 text-center mb-2">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <span key={d} className="text-[10px] text-text-muted font-medium">{d}</span>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {monthDays.map((day, i) => {
              if (day === null) return <div key={`e-${i}`} />
              const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
              const entry = dateToEntry[dateStr]
              return (
                <div
                  key={i}
                  className={`aspect-square rounded-lg flex flex-col items-center justify-center text-xs ${
                    entry ? "bg-surface" : "text-text-muted"
                  }`}
                >
                  <span className={`text-[10px] ${entry ? "text-text-muted" : "text-text-muted"}`}>{day}</span>
                  {entry && <span className="text-base leading-none mt-0.5">{MOOD_EMOJI[entry.mood] ?? "😐"}</span>}
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </motion.div>
  )
}
