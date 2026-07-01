import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchDailyNutrition, logMeal } from "../../api/queries/nutrition"
import { WidgetCard } from "./WidgetCard"
import { Apple, Plus } from "lucide-react"

interface Props { onExpand?: () => void }

export function NutritionWidget({ onExpand }: Props) {
  const [showQuick, setShowQuick] = useState(false)
  const [quickCal, setQuickCal] = useState("")
  const [quickDesc, setQuickDesc] = useState("")
  const qc = useQueryClient()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["nutrition"],
    queryFn: fetchDailyNutrition,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const logMut = useMutation({
    mutationFn: logMeal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nutrition"] })
      setShowQuick(false)
      setQuickCal("")
      setQuickDesc("")
    },
  })

  const cal = data?.totals?.calories ?? 0
  const target = data?.targets?.calories ?? 2000
  const pct = Math.min(Math.round((cal / target) * 100), 100)
  const protein = data?.totals?.protein ?? 0
  const proteinTarget = data?.targets?.protein_g ?? 150
  const hasData = (data?.meals?.length ?? 0) > 0

  const handleLog = () => {
    if (!quickCal.trim() || logMut.isPending) return
    logMut.mutate({
      meal_type: "snack",
      description: quickDesc.trim() || "Quick snack",
      calories: Number(quickCal),
    })
  }

  return (
    <WidgetCard
      icon={<Apple className="w-4 h-4" />}
      label="Nutrition"
      linkTo="/nutrition"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="No meals logged today"
      emptyCTA={
        <motion.button whileTap={{ scale: 0.97 }}
          onClick={() => setShowQuick(true)}
          className="inline-block px-4 py-1.5 rounded-full glass-strong text-apple-caption2 font-medium text-primary">
          Log a meal
        </motion.button>
      }
    >
      {/* Hero — cal ring */}
      <div className="flex items-center gap-3 mb-3">
        <div className="relative w-14 h-14 shrink-0">
          <svg className="w-14 h-14 -rotate-90" viewBox="0 0 36 36">
            <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--color-border)" strokeWidth="3" />
            <circle cx="18" cy="18" r="15.5" fill="none" stroke="url(#nutArc)" strokeWidth="3"
              strokeDasharray={`${pct} ${100 - pct}`} strokeLinecap="round" />
            <defs>
              <linearGradient id="nutArc" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#7c3aed" /><stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
            </defs>
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-text-primary">{pct}%</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-text-primary">{cal}</span>
            <span className="text-xs text-text-secondary">/ {target} kcal</span>
          </div>
          <div className="flex gap-2 mt-1">
            <span className="text-[10px] text-text-muted">P: {protein}/{proteinTarget}g</span>
          </div>
        </div>
      </div>

      {/* Cal bar */}
      <div className="h-1.5 bg-white/40 dark:bg-white/[0.06] rounded-full overflow-hidden mb-2">
        <div className="h-full rounded-full bg-violet-500 transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>

      {/* Quick log toggle */}
      <motion.button
        onClick={() => setShowQuick((p) => !p)}
        whileTap={{ scale: 0.95 }}
        className="w-full py-1.5 rounded-xl bg-white/10 dark:bg-white/[0.06] text-xs text-text-muted hover:text-text-primary transition-colors flex items-center justify-center gap-1.5">
        <Plus className="w-3 h-3" /> Quick meal
      </motion.button>

      {showQuick && (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
          className="overflow-hidden pt-2">
          <div className="flex gap-1.5">
            <input value={quickDesc} onChange={(e) => setQuickDesc(e.target.value)}
              placeholder="What did you eat?" autoFocus
              className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors" />
            <input value={quickCal} onChange={(e) => setQuickCal(e.target.value)} type="number"
              placeholder="Cal"
              className="w-16 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-2 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors tabular-nums" />
            <button onClick={handleLog} disabled={!quickCal.trim() || logMut.isPending}
              className="w-8 h-8 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0">
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}
    </WidgetCard>
  )
}
