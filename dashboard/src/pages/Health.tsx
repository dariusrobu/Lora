import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Moon, Droplets, Weight, Heart, TrendingUp, TrendingDown, Minus, Plus, CalendarDays } from "lucide-react"
import { Card, Button, Spinner } from "../components/ui"
import { fetchHealthSummary, logHealth } from "../api/queries/health"
import type { HealthLog, HealthSummary } from "../types"

const sleepQualities = ["great", "good", "neutral", "bad", "terrible"]

function fmtDate(d: string) {
  const dt = new Date(d + "T00:00:00")
  return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function Trend({ value, invert }: { value: number | undefined | null; invert?: boolean }) {
  if (value == null || value === 0) return null
  const positive = invert ? value < 0 : value > 0
  const negative = invert ? value > 0 : value < 0
  return (
    <span className={`text-[10px] flex items-center gap-0.5 ${positive || negative ? "text-text-secondary" : "text-text-muted"}`}>
      {positive ? <TrendingUp className="w-3 h-3" /> : negative ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
      {value > 0 ? "+" : ""}{value}
    </span>
  )
}

function CigaretteButton({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => onChange(Math.max(0, value - 1))}
        className="w-7 h-7 rounded-lg bg-surface border border-border text-text-secondary hover:text-text-primary hover:bg-surface flex items-center justify-center transition-all text-sm"
      >
        -
      </button>
      <span className="text-sm font-semibold text-text-primary w-5 text-center">{value}</span>
      <button
        onClick={() => onChange(value + 1)}
        className="w-7 h-7 rounded-lg bg-surface border border-border text-text-secondary hover:text-text-primary hover:bg-surface flex items-center justify-center transition-all text-sm"
      >
        +
      </button>
    </div>
  )
}

export default function Health() {
  const [sleep, setSleep] = useState("")
  const [water, setWater] = useState("")
  const [weight, setWeight] = useState("")
  const [cigarettes, setCigarettes] = useState(0)
  const [nutrition, setNutrition] = useState("")

  const [editingDate, setEditingDate] = useState<string | null>(null)
  const [editField, setEditField] = useState<string>("")
  const [editValue, setEditValue] = useState("")

  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: ["health"] })

  const { data, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealthSummary,
  })

  const logMut = useMutation({
    mutationFn: logHealth,
    onSuccess: () => {
      invalidate()
      setSleep("")
      setWater("")
      setWeight("")
      setCigarettes(0)
      setNutrition("")
    },
  })

  const { summary, history } = data ?? { summary: {} as HealthSummary, history: [] as HealthLog[] }

  const handleLog = () => {
    const payload: any = {}
    if (sleep.trim()) payload.sleep_hours = Number(sleep)
    if (water.trim()) payload.water_ml = Number(water)
    if (weight.trim()) payload.weight_kg = Number(weight)
    if (cigarettes > 0) payload.cigarettes = cigarettes
    if (nutrition) payload.nutrition = nutrition
    logMut.mutate(payload)
  }

  const last7 = history.slice(-7)
  const avgSleep7 = last7.filter((h) => h.sleep_hours != null).reduce((s, h) => s + h.sleep_hours!, 0) / Math.max(last7.filter((h) => h.sleep_hours != null).length, 1)
  const avgWater7 = last7.filter((h) => h.water_ml != null).reduce((s, h) => s + h.water_ml!, 0) / Math.max(last7.filter((h) => h.water_ml != null).length, 1)
  const avgCig7 = last7.filter((h) => h.cigarettes != null).reduce((s, h) => s + h.cigarettes!, 0) / Math.max(last7.filter((h) => h.cigarettes != null).length, 1)
  const todayEntry = history.length > 0 ? history[history.length - 1] : null

  if (isLoading) return <Spinner className="py-12" />

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Health</h1>
        <p className="text-text-secondary text-sm">Track your daily health metrics</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <Moon className="w-4 h-4 text-text-secondary" />
            <span className="text-xs text-text-secondary">Sleep</span>
          </div>
          <p className="text-xl font-bold">{summary.avg_sleep ?? "-"}</p>
          <p className="text-[10px] text-text-muted">h avg</p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <Droplets className="w-4 h-4 text-text-secondary" />
            <span className="text-xs text-text-secondary">Water</span>
          </div>
          <p className="text-xl font-bold">{summary.avg_water ?? "-"}</p>
          <p className="text-[10px] text-text-muted">ml avg</p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <Weight className="w-4 h-4 text-text-secondary" />
            <span className="text-xs text-text-secondary">Weight</span>
          </div>
          <div className="flex items-center gap-1.5">
            <p className="text-xl font-bold">{summary.recent_weight ?? "-"}</p>
            <Trend value={summary.recent_weight != null && summary.prev_weight != null ? Math.round((summary.recent_weight - summary.prev_weight) * 10) / 10 : undefined} invert />
          </div>
          <p className="text-[10px] text-text-muted">kg</p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <Heart className="w-4 h-4 text-text-secondary" />
            <span className="text-xs text-text-secondary">Cigarettes</span>
          </div>
          <p className="text-xl font-bold">{summary.avg_cigarettes != null ? summary.avg_cigarettes.toFixed(1) : "-"}</p>
          <p className="text-[10px] text-text-muted">/ day</p>
        </Card>
      </div>

      {/* Quick Log */}
      <Card className="p-4">
        <p className="text-xs font-medium text-text-secondary mb-3">Quick Log</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
          <input
            placeholder="Sleep (hrs)"
            type="number"
            value={sleep}
            onChange={(e) => setSleep(e.target.value)}
            className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
          />
          <input
            placeholder="Water (ml)"
            type="number"
            value={water}
            onChange={(e) => setWater(e.target.value)}
            className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
          />
          <input
            placeholder="Weight (kg)"
            type="number"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
          />
          <select
            value={nutrition}
            onChange={(e) => setNutrition(e.target.value)}
            className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary outline-none focus:border-primary/30 transition-colors"
          >
            <option value="">Nutrition quality</option>
            {sleepQualities.map((q) => (
              <option key={q} value={q} className="bg-bg">{q}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-4 mb-3">
          <span className="text-xs text-text-secondary">Cigarettes:</span>
          <CigaretteButton value={cigarettes} onChange={setCigarettes} />
        </div>
        <Button
          onClick={handleLog}
          disabled={logMut.isPending || (!sleep.trim() && !water.trim() && !weight.trim() && cigarettes === 0 && !nutrition)}
        >
          {logMut.isPending ? <Spinner size="sm" /> : "Log"}
        </Button>
      </Card>

      {/* History */}
      {history.length > 0 && (
        <div className="card-liquid shadow-apple-heavy">
          <div className="card-liquid-content overflow-hidden">
            <div className="px-4 py-3 border-b border-border/50">
            <h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Last 14 Days</h4>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border/30">
                  <th className="text-left py-2.5 px-4 font-medium">Date</th>
                  <th className="text-right py-2.5 font-medium">Sleep</th>
                  <th className="text-right py-2.5 font-medium">Water</th>
                  <th className="text-right py-2.5 font-medium">Weight</th>
                  <th className="text-right py-2.5 font-medium">🚬</th>
                  <th className="text-left py-2.5 pr-4 font-medium">Nutrition</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h: HealthLog, idx) => (
                  <tr key={h.log_date} className={`hover:bg-white/10 dark:hover:bg-white/[0.04] transition-colors group ${idx < history.length - 1 ? "border-b border-border/20" : ""}`}>
                    <td className="py-2.5 pl-4 text-text-secondary">
                      <span className="flex items-center gap-1">
                        <CalendarDays className="w-3 h-3" />
                        {fmtDate(h.log_date)}
                      </span>
                    </td>
                    <td className="text-right py-2.5 text-text-primary">{h.sleep_hours != null ? `${h.sleep_hours}h` : "-"}</td>
                    <td className="text-right py-2.5 text-text-primary">{h.water_ml != null ? `${h.water_ml}ml` : "-"}</td>
                    <td className="text-right py-2.5 text-text-primary">{h.weight_kg != null ? `${h.weight_kg}kg` : "-"}</td>
                    <td className="text-right py-2.5 text-text-primary">{h.cigarettes ?? "-"}</td>
                    <td className="py-2.5 pr-4">
                      {h.nutrition ? (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/40 dark:bg-white/[0.06] text-text-secondary">
                          {h.nutrition}
                        </span>
                      ) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </div>
        </div>
      )}

      {/* Weekly averages */}
      {last7.length > 0 && (
        <div className="card-liquid shadow-apple-heavy">
          <div className="card-liquid-content p-4">
            <p className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider mb-3">Weekly Averages</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div className="flex flex-col">
              <span className="text-apple-caption2 text-text-muted">Sleep</span>
              <span className="text-lg font-bold text-text-primary">{avgSleep7.toFixed(1)}h</span>
            </div>
            <div className="flex flex-col">
              <span className="text-apple-caption2 text-text-muted">Water</span>
              <span className="text-lg font-bold text-text-primary">{Math.round(avgWater7)}ml</span>
            </div>
            <div className="flex flex-col">
              <span className="text-apple-caption2 text-text-muted">Cigarettes</span>
              <span className="text-lg font-bold text-text-primary">{avgCig7.toFixed(1)}/d</span>
            </div>
            <div className="flex flex-col">
              <span className="text-apple-caption2 text-text-muted">Logged</span>
              <span className="text-lg font-bold text-text-primary">{last7.filter((h) => h.sleep_hours != null).length}/7 days</span>
          </div>
          </div>
        </div>
        </div>
      )}
    </motion.div>
  )
}
