import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Moon, Droplets, Scale, Heart, Sparkles, Plus, Minus, 
  CalendarDays, Flame, CheckCircle2, Circle, TrendingUp, 
  TrendingDown, Activity
} from "lucide-react"
import { Spinner } from "../components/ui"
import { fetchHealthSummary, logHealth } from "../api/queries/health"
import { fetchSkills, logSkill } from "../api/queries/skills"
import type { HealthLog, HealthSummary, Skill } from "../types"

const NUTRITION_QUALITIES = [
  { id: "great", label: "Excelentă", icon: "🥗" },
  { id: "good", label: "Bună", icon: "🥑" },
  { id: "neutral", label: "Medie", icon: "🥪" },
  { id: "bad", label: "Fast-food", icon: "🍕" },
]

function fmtDate(d: string) {
  const dt = new Date(d + "T00:00:00")
  return dt.toLocaleDateString("ro-RO", { month: "short", day: "numeric" })
}

export default function Health() {
  const [sleep, setSleep] = useState("")
  const [water, setWater] = useState("")
  const [weight, setWeight] = useState("")
  const [cigarettes, setCigarettes] = useState(0)
  const [nutrition, setNutrition] = useState("")
  const [togglingHabit, setTogglingHabit] = useState<Set<string>>(new Set())

  const qc = useQueryClient()
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["health"] })
    qc.invalidateQueries({ queryKey: ["health-summary"] })
  }

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealthSummary,
  })

  const { data: skillsData } = useQuery({
    queryKey: ["skills"],
    queryFn: fetchSkills,
    staleTime: 30_000,
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

  const logSkillMut = useMutation({
    mutationFn: (name: string) => logSkill(name, 1),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skills"] })
      setTimeout(() => setTogglingHabit(new Set()), 400)
    },
  })

  const { summary, history } = data ?? { 
    summary: { avg_sleep: 7.5, avg_water: 1800, recent_weight: 65, total_days: 0 } as HealthSummary, 
    history: [] as HealthLog[] 
  }

  const handleLog = () => {
    const payload: any = {}
    if (sleep.trim()) payload.sleep_hours = Number(sleep)
    if (water.trim()) payload.water_ml = Number(water)
    if (weight.trim()) payload.weight_kg = Number(weight)
    if (cigarettes > 0) payload.cigarettes = cigarettes
    if (nutrition) payload.nutrition = nutrition
    logMut.mutate(payload)
  }

  const handleHabitToggle = (name: string) => {
    setTogglingHabit((prev) => new Set(prev).add(name))
    logSkillMut.mutate(name)
  }

  const todayStr = useMemo(() => new Date().toISOString().split("T")[0], [])

  const displayedHabits = useMemo(() => {
    if (skillsData && skillsData.length > 0) {
      return skillsData.map((s: Skill) => ({
        id: s.id,
        name: s.name,
        streak: s.streak ?? 1,
        doneToday: s.last_log_date === todayStr || togglingHabit.has(s.name),
      }))
    }
    return [
      { id: 101, name: "Meditație", streak: 3, doneToday: togglingHabit.has("Meditație") },
      { id: 102, name: "Citit 20m", streak: 7, doneToday: togglingHabit.has("Citit 20m") },
      { id: 103, name: "Sport / Sală", streak: 5, doneToday: togglingHabit.has("Sport / Sală") },
    ]
  }, [skillsData, todayStr, togglingHabit])

  const last7 = history.slice(-7)
  const avgSleep7 = last7.filter((h) => h.sleep_hours != null).reduce((s, h) => s + h.sleep_hours!, 0) / Math.max(last7.filter((h) => h.sleep_hours != null).length, 1)
  const avgWater7 = last7.filter((h) => h.water_ml != null).reduce((s, h) => s + h.water_ml!, 0) / Math.max(last7.filter((h) => h.water_ml != null).length, 1)

  return (
    <motion.div 
      initial={{ opacity: 0, y: 8 }} 
      animate={{ opacity: 1, y: 0 }} 
      className="max-w-4xl mx-auto space-y-6 pb-20"
    >
      {/* Aurora Glow & Header */}
      <div className="relative pt-2 pb-1">
        <div className="absolute -top-10 left-0 w-72 h-40 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <Activity className="w-4 h-4" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white">Sănătate & Obiceiuri</h1>
            </div>
            <p className="text-zinc-400 text-xs sm:text-sm pl-10">
              Monitorizare biometrică, target zilnic de hidratare și ritm circadian
            </p>
          </div>
        </div>
      </div>

      {/* 4 Prominent KPI Metrics (Unboxed Canvas) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-3xl bg-white/[0.02] border border-white/[0.05] divide-y sm:divide-y-0 sm:divide-x divide-white/[0.06] backdrop-blur-xl">
        {/* 1. Somn */}
        <div className="flex flex-col items-center sm:items-start sm:pl-3 pb-3 sm:pb-0">
          <div className="flex items-center gap-1.5 mb-1 text-zinc-400">
            <Moon className="w-4 h-4 text-indigo-400" />
            <span className="text-[11px] font-bold uppercase tracking-wider">Somn Mediu</span>
          </div>
          <span className="text-3xl sm:text-4xl font-black text-indigo-400 tabular-nums tracking-tight">
            {summary.avg_sleep != null ? `${summary.avg_sleep}h` : "7.5h"}
          </span>
          <span className="text-[11px] text-zinc-500 mt-0.5">/ 8h optim</span>
        </div>

        {/* 2. Hidratare */}
        <div className="flex flex-col items-center sm:items-start sm:px-4 pb-3 sm:pb-0">
          <div className="flex items-center gap-1.5 mb-1 text-zinc-400">
            <Droplets className="w-4 h-4 text-sky-400" />
            <span className="text-[11px] font-bold uppercase tracking-wider">Apă Medie</span>
          </div>
          <span className="text-3xl sm:text-4xl font-black text-sky-400 tabular-nums tracking-tight">
            {summary.avg_water != null 
              ? summary.avg_water >= 1000 ? `${(summary.avg_water / 1000).toFixed(1)}L` : `${summary.avg_water}ml`
              : "1.8L"}
          </span>
          <span className="text-[11px] text-zinc-500 mt-0.5">target 2.5L</span>
        </div>

        {/* 3. Greutate */}
        <div className="flex flex-col items-center sm:items-start sm:px-4 pt-3 sm:pt-0">
          <div className="flex items-center gap-1.5 mb-1 text-zinc-400">
            <Scale className="w-4 h-4 text-emerald-400" />
            <span className="text-[11px] font-bold uppercase tracking-wider">Greutate</span>
          </div>
          <span className="text-3xl sm:text-4xl font-black text-emerald-400 tabular-nums tracking-tight">
            {summary.recent_weight != null ? `${summary.recent_weight}kg` : "65.0kg"}
          </span>
          <span className="text-[11px] text-emerald-400/80 font-medium mt-0.5 capitalize">
            {summary.weight_trend ?? "stabil"}
          </span>
        </div>

        {/* 4. Monitorizare */}
        <div className="flex flex-col items-center sm:items-start sm:px-4 pt-3 sm:pt-0">
          <div className="flex items-center gap-1.5 mb-1 text-zinc-400">
            <Heart className="w-4 h-4 text-rose-400" />
            <span className="text-[11px] font-bold uppercase tracking-wider">Înregistrări</span>
          </div>
          <span className="text-3xl sm:text-4xl font-black text-white tabular-nums tracking-tight">
            {history.length}
          </span>
          <span className="text-[11px] text-zinc-500 mt-0.5">zile logate</span>
        </div>
      </div>

      {/* Habits & Daily Streaks Grid */}
      <div className="p-4 sm:p-5 rounded-3xl bg-white/[0.02] border border-white/[0.06] backdrop-blur-xl space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
            <Flame className="w-4 h-4 text-orange-400" /> Obiceiuri Zilnice (Habits)
          </span>
          <span className="text-xs text-zinc-500 font-medium">Bifează ce ai îndeplinit azi</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {displayedHabits.map((h) => (
            <motion.div
              key={h.name}
              whileTap={{ scale: 0.97 }}
              onClick={() => handleHabitToggle(h.name)}
              className={`flex items-center justify-between p-3 rounded-2xl border cursor-pointer transition-all ${
                h.doneToday
                  ? "bg-emerald-500/[0.08] border-emerald-500/30 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.06)]"
                  : "bg-white/[0.02] hover:bg-white/[0.04] border-white/[0.05] text-zinc-300 hover:text-white"
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                  h.doneToday ? "text-emerald-400" : "text-zinc-500"
                }`}>
                  {h.doneToday ? (
                    <CheckCircle2 className="w-5 h-5" />
                  ) : (
                    <Circle className="w-4 h-4" />
                  )}
                </div>
                <span className={`text-sm font-semibold truncate ${
                  h.doneToday ? "line-through opacity-75" : ""
                }`}>
                  {h.name}
                </span>
              </div>

              <div className="flex items-center gap-1 shrink-0 ml-2 text-xs font-bold text-orange-400/90">
                <Flame className="w-3.5 h-3.5" />
                <span>{h.streak}d</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Quick Log Form (Linear Style) */}
      <div className="p-4 sm:p-5 rounded-3xl bg-white/[0.02] border border-white/[0.06] backdrop-blur-xl space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-indigo-400" /> Înregistrare Rapidă (Azi)
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Somn */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-zinc-400 flex items-center gap-1">
              <Moon className="w-3 h-3 text-indigo-400" /> Somn (ore)
            </label>
            <input
              placeholder="ex: 7.5"
              type="number"
              step="0.5"
              value={sleep}
              onChange={(e) => setSleep(e.target.value)}
              className="w-full bg-white/[0.03] hover:bg-white/[0.05] focus:bg-white/[0.07] border border-white/[0.08] focus:border-indigo-400/40 rounded-xl py-2 px-3 text-sm text-white placeholder:text-zinc-500 outline-none transition-all"
            />
          </div>

          {/* Apă */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-zinc-400 flex items-center justify-between">
              <span className="flex items-center gap-1">
                <Droplets className="w-3 h-3 text-sky-400" /> Apă (ml)
              </span>
              <span className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setWater(String((Number(water) || 0) + 250))}
                  className="px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-300 text-[10px] font-bold"
                >
                  +250
                </button>
                <button
                  type="button"
                  onClick={() => setWater(String((Number(water) || 0) + 500))}
                  className="px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-300 text-[10px] font-bold"
                >
                  +500
                </button>
              </span>
            </label>
            <input
              placeholder="ex: 2000"
              type="number"
              step="250"
              value={water}
              onChange={(e) => setWater(e.target.value)}
              className="w-full bg-white/[0.03] hover:bg-white/[0.05] focus:bg-white/[0.07] border border-white/[0.08] focus:border-sky-400/40 rounded-xl py-2 px-3 text-sm text-white placeholder:text-zinc-500 outline-none transition-all"
            />
          </div>

          {/* Greutate */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-zinc-400 flex items-center gap-1">
              <Scale className="w-3 h-3 text-emerald-400" /> Greutate (kg)
            </label>
            <input
              placeholder="ex: 65.5"
              type="number"
              step="0.1"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className="w-full bg-white/[0.03] hover:bg-white/[0.05] focus:bg-white/[0.07] border border-white/[0.08] focus:border-emerald-400/40 rounded-xl py-2 px-3 text-sm text-white placeholder:text-zinc-500 outline-none transition-all"
            />
          </div>
        </div>

        {/* Calitate Nutriție & Țigări */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
          {/* Nutrition Quality Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
            <span className="text-[11px] text-zinc-400 font-medium mr-1">Nutriție:</span>
            {NUTRITION_QUALITIES.map((q) => {
              const isSelected = nutrition === q.id
              return (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => setNutrition(isSelected ? "" : q.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 shrink-0 ${
                    isSelected
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
                      : "bg-white/[0.03] text-zinc-400 hover:text-white border border-white/[0.05]"
                  }`}
                >
                  <span>{q.icon}</span>
                  <span>{q.label}</span>
                </button>
              )
            })}
          </div>

          {/* Cigarettes Counter */}
          <div className="flex items-center gap-3 bg-white/[0.02] px-3 py-1.5 rounded-xl border border-white/[0.04] self-start sm:self-auto">
            <span className="text-xs text-zinc-400 flex items-center gap-1">
              <span>🚬</span> Țigări:
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCigarettes(Math.max(0, cigarettes - 1))}
                className="w-6 h-6 rounded-md bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 flex items-center justify-center text-xs"
              >
                -
              </button>
              <span className="text-xs font-bold text-white w-4 text-center tabular-nums">{cigarettes}</span>
              <button
                type="button"
                onClick={() => setCigarettes(cigarettes + 1)}
                className="w-6 h-6 rounded-md bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 flex items-center justify-center text-xs font-bold"
              >
                +
              </button>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="pt-2 flex justify-end">
          <motion.button
            onClick={handleLog}
            disabled={logMut.isPending || (!sleep.trim() && !water.trim() && !weight.trim() && cigarettes === 0 && !nutrition)}
            whileTap={{ scale: 0.96 }}
            className="px-6 py-2.5 rounded-2xl bg-gradient-to-tr from-primary to-accent text-white font-semibold text-xs disabled:opacity-30 transition-all flex items-center gap-2 shadow-[0_2px_14px_rgba(99,102,241,0.35)] hover:scale-[1.02]"
          >
            {logMut.isPending ? (
              <Spinner size="sm" />
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Salvează metricele zilei</span>
              </>
            )}
          </motion.button>
        </div>
      </div>

      {/* History Table (Cardless Unboxed) */}
      {history.length > 0 && (
        <div className="p-4 sm:p-5 rounded-3xl bg-white/[0.02] border border-white/[0.05] backdrop-blur-xl space-y-3">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
              <CalendarDays className="w-4 h-4 text-indigo-400" /> Istoric Biometric (Ultimele 14 Zile)
            </h4>
          </div>

          <div className="overflow-x-auto no-scrollbar">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-500 border-b border-white/[0.05]">
                  <th className="text-left py-2.5 px-3 font-semibold uppercase text-[10px] tracking-wider">Data</th>
                  <th className="text-right py-2.5 px-3 font-semibold uppercase text-[10px] tracking-wider">Somn</th>
                  <th className="text-right py-2.5 px-3 font-semibold uppercase text-[10px] tracking-wider">Apă</th>
                  <th className="text-right py-2.5 px-3 font-semibold uppercase text-[10px] tracking-wider">Greutate</th>
                  <th className="text-right py-2.5 px-3 font-semibold uppercase text-[10px] tracking-wider">Țigări</th>
                  <th className="text-left py-2.5 px-3 font-semibold uppercase text-[10px] tracking-wider">Nutriție</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {history.map((h: HealthLog) => (
                  <tr key={h.log_date} className="hover:bg-white/[0.03] transition-colors">
                    <td className="py-3 px-3 text-zinc-300 font-medium">
                      <span className="flex items-center gap-1.5">
                        <CalendarDays className="w-3.5 h-3.5 text-zinc-500" />
                        {fmtDate(h.log_date)}
                      </span>
                    </td>
                    <td className="text-right py-3 px-3 text-indigo-300 font-bold tabular-nums">
                      {h.sleep_hours != null ? `${h.sleep_hours}h` : "-"}
                    </td>
                    <td className="text-right py-3 px-3 text-sky-300 font-bold tabular-nums">
                      {h.water_ml != null ? `${h.water_ml}ml` : "-"}
                    </td>
                    <td className="text-right py-3 px-3 text-emerald-300 font-bold tabular-nums">
                      {h.weight_kg != null ? `${h.weight_kg}kg` : "-"}
                    </td>
                    <td className="text-right py-3 px-3 text-zinc-400 font-medium tabular-nums">
                      {h.cigarettes ?? "-"}
                    </td>
                    <td className="py-3 px-3">
                      {h.nutrition ? (
                        <span className="px-2 py-0.5 rounded-full bg-white/[0.04] text-zinc-300 text-[10px] font-medium border border-white/[0.04]">
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
      )}
    </motion.div>
  )
}

