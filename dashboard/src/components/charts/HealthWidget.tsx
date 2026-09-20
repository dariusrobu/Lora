import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchHealthSummary, logHealth } from "../../api/queries/health"
import { fetchSkills, logSkill } from "../../api/queries/skills"
import { WidgetCard } from "./WidgetCard"
import { 
  Heart, Moon, Droplets, Scale, Plus, Minus, Check, 
  Sparkles, Flame, CheckCircle2, Circle
} from "lucide-react"

interface Props { onExpand?: () => void }

const DEFAULT_HABITS = [
  { id: 101, name: "Meditație", streak: 3 },
  { id: 102, name: "Citit 20m", streak: 7 },
  { id: 103, name: "Sport / Sală", streak: 5 },
]

export function HealthWidget({ onExpand }: Props) {
  const [togglingHabit, setTogglingHabit] = useState<Set<string>>(new Set())
  const qc = useQueryClient()

  // Health summary query
  const { data: healthData, isLoading: healthLoading, isError: healthError, refetch: refetchHealth } = useQuery({
    queryKey: ["health-summary"],
    queryFn: fetchHealthSummary,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  // Habits / Skills query
  const { data: skillsData, refetch: refetchSkills } = useQuery({
    queryKey: ["skills"],
    queryFn: fetchSkills,
    staleTime: 30_000,
  })

  const logHealthMut = useMutation({
    mutationFn: logHealth,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["health-summary"] }),
  })

  const logSkillMut = useMutation({
    mutationFn: (name: string) => logSkill(name, 1),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skills"] })
      setTimeout(() => setTogglingHabit(new Set()), 400)
    },
  })

  const todayLog = healthData?.history?.[0]
  const summary = healthData?.summary

  // Sleep: use today's log or average
  const sleepHours = todayLog?.sleep_hours ?? summary?.avg_sleep ?? 7.5
  const sleepTarget = 8.0
  const sleepPct = Math.min(100, Math.round((sleepHours / sleepTarget) * 100))

  // Water: use today's log or average
  const waterMl = todayLog?.water_ml ?? summary?.avg_water ?? 1800
  const waterTarget = 2500
  const waterPct = Math.min(100, Math.round((waterMl / waterTarget) * 100))

  // Weight
  const weightKg = todayLog?.weight_kg ?? summary?.recent_weight ?? 65.0
  const weightTrend = summary?.weight_trend ?? "stabil"

  // Cigarettes
  const cigs = todayLog?.cigarettes ?? 0

  // Composite health activity percentage
  const compositeScore = Math.round((sleepPct + waterPct) / 2)

  // Apple Health concentric ring circumference calculations
  // Outer ring (Sleep): radius = 48, circum ~ 301.59
  const rOuter = 48
  const cOuter = 2 * Math.PI * rOuter
  const offsetOuter = cOuter * (1 - Math.min(1, sleepPct / 100))

  // Inner ring (Water): radius = 35, circum ~ 219.91
  const rInner = 35
  const cInner = 2 * Math.PI * rInner
  const offsetInner = cInner * (1 - Math.min(1, waterPct / 100))

  // Quick actions
  const adjustSleep = (delta: number) => {
    const current = todayLog?.sleep_hours ?? sleepHours
    const updated = Math.max(0, Math.min(14, Number((current + delta).toFixed(1))))
    logHealthMut.mutate({ sleep_hours: updated })
  }

  const boostWater = (amount: number) => {
    const current = todayLog?.water_ml ?? waterMl
    logHealthMut.mutate({ water_ml: current + amount })
  }

  const toggleCig = (delta: number) => {
    const current = todayLog?.cigarettes ?? 0
    logHealthMut.mutate({ cigarettes: Math.max(0, current + delta) })
  }

  // Habits handling
  const todayStr = useMemo(() => new Date().toISOString().split("T")[0], [])
  const displayedHabits = useMemo(() => {
    if (skillsData && skillsData.length > 0) {
      return skillsData.slice(0, 3).map((s) => ({
        id: s.id,
        name: s.name,
        streak: s.streak ?? 1,
        doneToday: s.last_log_date === todayStr || togglingHabit.has(s.name),
      }))
    }
    return DEFAULT_HABITS.map((h) => ({
      ...h,
      doneToday: togglingHabit.has(h.name),
    }))
  }, [skillsData, todayStr, togglingHabit])

  const handleHabitToggle = (name: string) => {
    setTogglingHabit((prev) => new Set(prev).add(name))
    logSkillMut.mutate(name)
  }

  return (
    <WidgetCard
      icon={<Heart className="w-4 h-4" />}
      label="Health & Habits"
      linkTo="/health"
      onExpand={onExpand}
      isLoading={healthLoading}
      isError={healthError}
      onRetry={() => {
        refetchHealth()
        refetchSkills()
      }}
    >
      {/* Top Hero Section: Dual Apple Health Concentric Rings + 3 Key Prominent Metrics */}
      <div className="flex flex-col sm:flex-row items-center gap-5 p-3 rounded-2xl bg-white/[0.015] border border-white/[0.04] mb-4">
        {/* Dual Concentric Rings (Sleep + Water) */}
        <div className="relative w-28 h-28 shrink-0 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
            <defs>
              {/* Outer Sleep Ring Gradient */}
              <linearGradient id="sleepRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6366F1" />
                <stop offset="100%" stopColor="#A855F7" />
              </linearGradient>
              {/* Inner Water Ring Gradient */}
              <linearGradient id="waterRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#06B6D4" />
                <stop offset="100%" stopColor="#38BDF8" />
              </linearGradient>
            </defs>

            {/* Sleep Outer Track */}
            <circle
              cx="60"
              cy="60"
              r={rOuter}
              fill="none"
              stroke="#6366F1"
              strokeWidth="9"
              strokeOpacity="0.12"
            />
            {/* Sleep Outer Active Arc */}
            <motion.circle
              cx="60"
              cy="60"
              r={rOuter}
              fill="none"
              stroke="url(#sleepRingGrad)"
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={cOuter}
              initial={{ strokeDashoffset: cOuter }}
              animate={{ strokeDashoffset: offsetOuter }}
              transition={{ duration: 0.9, ease: "easeOut" }}
            />

            {/* Water Inner Track */}
            <circle
              cx="60"
              cy="60"
              r={rInner}
              fill="none"
              stroke="#06B6D4"
              strokeWidth="9"
              strokeOpacity="0.12"
            />
            {/* Water Inner Active Arc */}
            <motion.circle
              cx="60"
              cy="60"
              r={rInner}
              fill="none"
              stroke="url(#waterRingGrad)"
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={cInner}
              initial={{ strokeDashoffset: cInner }}
              animate={{ strokeDashoffset: offsetInner }}
              transition={{ duration: 0.9, ease: "easeOut", delay: 0.1 }}
            />
          </svg>

          {/* Center Activity Score */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-lg font-black text-white tabular-nums tracking-tight">
              {compositeScore}%
            </span>
            <span className="text-[9px] font-semibold text-zinc-400 uppercase tracking-widest">
              Scor
            </span>
          </div>
        </div>

        {/* 3 Prominent Metrics Columns */}
        <div className="grid grid-cols-3 gap-2 sm:gap-3 flex-1 w-full divide-x divide-white/[0.06]">
          {/* 1. Sleep */}
          <div className="flex flex-col items-center sm:items-start pl-1 sm:pl-2">
            <div className="flex items-center gap-1 mb-1 text-zinc-400">
              <Moon className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider">Somn</span>
            </div>
            <span className="text-xl sm:text-2xl font-black text-indigo-400 tabular-nums tracking-tight">
              {sleepHours}h
            </span>
            <span className="text-[10px] text-zinc-500 font-medium mt-0.5">
              / {sleepTarget}h ({sleepPct}%)
            </span>
            {/* Quick Adjust Buttons */}
            <div className="flex items-center gap-1 mt-2">
              <button
                onClick={() => adjustSleep(-0.5)}
                disabled={logHealthMut.isPending}
                className="w-5 h-5 rounded-md bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-white flex items-center justify-center text-[10px] transition-all"
                title="-0.5 ore"
              >
                <Minus className="w-2.5 h-2.5" />
              </button>
              <button
                onClick={() => adjustSleep(0.5)}
                disabled={logHealthMut.isPending}
                className="w-5 h-5 rounded-md bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 flex items-center justify-center text-[10px] transition-all"
                title="+0.5 ore"
              >
                <Plus className="w-2.5 h-2.5" />
              </button>
            </div>
          </div>

          {/* 2. Water */}
          <div className="flex flex-col items-center sm:items-start px-2 sm:px-3">
            <div className="flex items-center gap-1 mb-1 text-zinc-400">
              <Droplets className="w-3.5 h-3.5 text-sky-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider">Apă</span>
            </div>
            <span className="text-xl sm:text-2xl font-black text-sky-400 tabular-nums tracking-tight">
              {waterMl >= 1000 ? `${(waterMl / 1000).toFixed(1)}L` : `${waterMl}ml`}
            </span>
            <span className="text-[10px] text-zinc-500 font-medium mt-0.5">
              {waterPct}% din target
            </span>
            {/* Quick Booster Buttons */}
            <div className="flex items-center gap-1 mt-2">
              <button
                onClick={() => boostWater(250)}
                disabled={logHealthMut.isPending}
                className="px-1.5 py-0.5 rounded-md bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 text-[10px] font-bold transition-all"
                title="+250 ml (pahar)"
              >
                +250
              </button>
              <button
                onClick={() => boostWater(500)}
                disabled={logHealthMut.isPending}
                className="px-1.5 py-0.5 rounded-md bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 text-[10px] font-bold transition-all"
                title="+500 ml (sticlă)"
              >
                +500
              </button>
            </div>
          </div>

          {/* 3. Weight */}
          <div className="flex flex-col items-center sm:items-start px-2 sm:px-3">
            <div className="flex items-center gap-1 mb-1 text-zinc-400">
              <Scale className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider">Greutate</span>
            </div>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 tabular-nums tracking-tight">
              {weightKg}kg
            </span>
            <span className="text-[10px] text-emerald-400/80 font-medium mt-0.5 capitalize">
              {weightTrend}
            </span>
            <div className="mt-2 text-[10px] text-zinc-500 flex items-center gap-1">
              <Sparkles className="w-2.5 h-2.5 text-emerald-400" /> optim
            </div>
          </div>
        </div>
      </div>

      {/* Habits & Daily Streaks Section */}
      <div className="space-y-1.5 mb-3">
        <div className="flex items-center justify-between px-1 mb-1">
          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1">
            <Flame className="w-3 h-3 text-orange-400" /> Obiceiuri & Streaks
          </span>
          <span className="text-[10px] text-zinc-500 font-medium">Bifează pentru azi</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {displayedHabits.map((habit) => (
            <motion.div
              key={habit.name}
              whileTap={{ scale: 0.96 }}
              onClick={() => handleHabitToggle(habit.name)}
              className={`flex items-center justify-between p-2.5 rounded-xl border cursor-pointer transition-all ${
                habit.doneToday
                  ? "bg-emerald-500/[0.07] border-emerald-500/25 text-emerald-300"
                  : "bg-white/[0.02] hover:bg-white/[0.04] border-white/[0.05] text-zinc-300 hover:text-white"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 ${
                  habit.doneToday ? "text-emerald-400" : "text-zinc-500"
                }`}>
                  {habit.doneToday ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : (
                    <Circle className="w-3.5 h-3.5" />
                  )}
                </div>
                <span className={`text-xs font-semibold truncate ${
                  habit.doneToday ? "line-through opacity-80" : ""
                }`}>
                  {habit.name}
                </span>
              </div>

              <div className="flex items-center gap-1 shrink-0 ml-1 text-[10px] font-bold text-orange-400/90">
                <Flame className="w-2.5 h-2.5" />
                <span>{habit.streak}d</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Subtle Cigarette Counter (Harm Reduction) */}
      <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-white/[0.015] border border-white/[0.03]">
        <div className="flex items-center gap-2">
          <span className="text-xs">🚬</span>
          <span className="text-[11px] text-zinc-400">Țigări azi:</span>
          <span className="text-xs font-bold text-white tabular-nums">{cigs}</span>
        </div>
        <div className="flex items-center gap-1">
          {cigs > 0 && (
            <button
              onClick={() => toggleCig(-1)}
              disabled={logHealthMut.isPending}
              className="px-2 py-0.5 rounded-md bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 text-[10px] font-medium transition-colors"
            >
              -1
            </button>
          )}
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={() => toggleCig(1)}
            disabled={logHealthMut.isPending}
            className="px-2.5 py-0.5 rounded-md bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-[10px] font-semibold transition-colors"
          >
            +1
          </motion.button>
        </div>
      </div>
    </WidgetCard>
  )
}

