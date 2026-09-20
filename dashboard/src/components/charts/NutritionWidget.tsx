import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { fetchDailyNutrition, logMeal } from "../../api/queries/nutrition"
import { WidgetCard } from "./WidgetCard"
import { Apple, Plus, Flame, Utensils, Sparkles, Check } from "lucide-react"

interface Props { onExpand?: () => void }

export function NutritionWidget({ onExpand }: Props) {
  const [showQuick, setShowQuick] = useState(false)
  const [quickCal, setQuickCal] = useState("")
  const [quickDesc, setQuickDesc] = useState("")
  const [quickType, setQuickType] = useState<"breakfast" | "lunch" | "dinner" | "snack">("snack")
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
  const target = data?.targets?.calories ?? 2200
  const pct = target > 0 ? Math.min(100, Math.round((cal / target) * 100)) : 0

  const protein = data?.totals?.protein ?? 0
  const proteinTarget = data?.targets?.protein_g ?? 140
  const proteinPct = proteinTarget > 0 ? Math.min(100, Math.round((protein / proteinTarget) * 100)) : 0

  const carbs = data?.totals?.carbs ?? 0
  const carbsTarget = data?.targets?.carbs_g ?? 240
  const carbsPct = carbsTarget > 0 ? Math.min(100, Math.round((carbs / carbsTarget) * 100)) : 0

  const fat = data?.totals?.fat ?? 0
  const fatTarget = data?.targets?.fat_g ?? 70
  const fatPct = fatTarget > 0 ? Math.min(100, Math.round((fat / fatTarget) * 100)) : 0

  const meals = data?.meals ?? []
  const hasData = meals.length > 0 || cal > 0

  const handleLog = () => {
    if (!quickCal.trim() || logMut.isPending) return
    logMut.mutate({
      meal_type: quickType,
      description: quickDesc.trim() || "Gustare",
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
      emptyMessage="Nicio masă înregistrată azi"
      emptyCTA={
        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={() => setShowQuick(true)}
          className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs font-medium text-emerald-400 hover:text-white transition-all"
        >
          <Plus className="w-3.5 h-3.5" /> Înregistrează o masă
        </motion.button>
      }
    >
      {/* Hero: Big Calorie Ring + Macros Overview */}
      <div className="flex flex-col sm:flex-row items-center gap-6 mb-5 p-4 rounded-2xl bg-white/[0.015] border border-white/[0.04]">
        {/* Animated Calorie Progress Ring */}
        <div className="relative w-28 h-28 sm:w-32 sm:h-32 shrink-0 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="none"
              stroke="rgba(255, 255, 255, 0.05)"
              strokeWidth="8"
            />
            {pct > 0 && (
              <motion.circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="url(#nutriRingGradient)"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={251.327}
                initial={{ strokeDashoffset: 251.327 }}
                animate={{ strokeDashoffset: 251.327 - (251.327 * pct) / 100 }}
                transition={{ duration: 1, ease: [0.34, 1.56, 0.64, 1] }}
              />
            )}
            <defs>
              <linearGradient id="nutriRingGradient" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#10B981" />
                <stop offset="60%" stopColor="#6366F1" />
                <stop offset="100%" stopColor="#A855F7" />
              </linearGradient>
            </defs>
          </svg>

          {/* Center Content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <motion.span
              key={cal}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="text-2xl sm:text-3xl font-black text-white tracking-tight tabular-nums"
            >
              {cal}
            </motion.span>
            <span className="text-[10px] font-bold text-emerald-400/90 uppercase tracking-widest mt-0.5">
              / {target} kcal
            </span>
          </div>
        </div>

        {/* 3 Macro-nutrients Columns (P / C / F) */}
        <div className="grid grid-cols-3 gap-3 w-full sm:divide-x sm:divide-white/[0.06]">
          {/* Protein */}
          <div className="flex flex-col items-center sm:items-start sm:pl-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 mb-1">
              Proteine
            </span>
            <span className="text-xl sm:text-2xl font-black text-white tabular-nums tracking-tight">
              {protein}g
            </span>
            <div className="w-full bg-white/[0.06] h-1 rounded-full overflow-hidden mt-1.5">
              <div
                className="bg-indigo-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${proteinPct}%` }}
              />
            </div>
            <span className="text-[9px] text-zinc-500 mt-1">{proteinPct}% din {proteinTarget}g</span>
          </div>

          {/* Carbs */}
          <div className="flex flex-col items-center sm:items-start sm:px-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400 mb-1">
              Carbohidrați
            </span>
            <span className="text-xl sm:text-2xl font-black text-white tabular-nums tracking-tight">
              {carbs}g
            </span>
            <div className="w-full bg-white/[0.06] h-1 rounded-full overflow-hidden mt-1.5">
              <div
                className="bg-amber-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${carbsPct}%` }}
              />
            </div>
            <span className="text-[9px] text-zinc-500 mt-1">{carbsPct}% din {carbsTarget}g</span>
          </div>

          {/* Fat */}
          <div className="flex flex-col items-center sm:items-start sm:px-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400 mb-1">
              Grăsimi
            </span>
            <span className="text-xl sm:text-2xl font-black text-white tabular-nums tracking-tight">
              {fat}g
            </span>
            <div className="w-full bg-white/[0.06] h-1 rounded-full overflow-hidden mt-1.5">
              <div
                className="bg-rose-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${fatPct}%` }}
              />
            </div>
            <span className="text-[9px] text-zinc-500 mt-1">{fatPct}% din {fatTarget}g</span>
          </div>
        </div>
      </div>

      {/* Recent Meals List */}
      {meals.length > 0 && (
        <div className="space-y-1.5 mb-4">
          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 px-1 block">
            Mese Înregistrate Azi ({meals.length})
          </span>
          {meals.slice(0, 3).map((m, idx) => (
            <motion.div
              key={m.id || idx}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04 }}
              className="flex items-center justify-between p-2.5 rounded-xl hover:bg-white/[0.035] border border-transparent hover:border-white/[0.04] transition-all"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-6 h-6 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-xs shrink-0">
                  <Utensils className="w-3 h-3" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-zinc-200 truncate capitalize">
                    {m.description || m.meal_type}
                  </p>
                  <p className="text-[10px] text-zinc-500 capitalize">{m.meal_type}</p>
                </div>
              </div>
              <span className="text-xs font-bold text-emerald-400 tabular-nums shrink-0 ml-2">
                +{m.calories} kcal
              </span>
            </motion.div>
          ))}
        </div>
      )}

      {/* Quick Meal Input (Linear Style) */}
      <AnimatePresence>
        {showQuick ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="pt-2 border-t border-white/[0.05] space-y-2"
          >
            <div className="flex gap-2">
              <input
                value={quickDesc}
                onChange={(e) => setQuickDesc(e.target.value)}
                placeholder="Ce ai mâncat? (ex: Omletă cu pâine)"
                autoFocus
                className="flex-1 bg-white/[0.03] border border-white/[0.08] focus:border-indigo-400/40 rounded-xl px-3 py-2 text-xs text-white placeholder:text-zinc-500 outline-none transition-all"
              />
              <input
                value={quickCal}
                onChange={(e) => setQuickCal(e.target.value)}
                type="number"
                placeholder="Calorii"
                className="w-24 bg-white/[0.03] border border-white/[0.08] focus:border-indigo-400/40 rounded-xl px-3 py-2 text-xs text-white placeholder:text-zinc-500 outline-none transition-all tabular-nums"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <div className="flex gap-1">
                {(["breakfast", "lunch", "dinner", "snack"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setQuickType(t)}
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-bold capitalize transition-all ${
                      quickType === t
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "text-zinc-500 hover:text-zinc-300"
                    }`}
                  >
                    {t === "breakfast" ? "mic dejun" : t === "lunch" ? "prânz" : t === "dinner" ? "cină" : "gustare"}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowQuick(false)}
                  className="px-2.5 py-1 text-xs text-zinc-400 hover:text-white"
                >
                  Anulează
                </button>
                <button
                  onClick={handleLog}
                  disabled={!quickCal.trim() || logMut.isPending}
                  className="px-3 py-1 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-xs font-bold text-white shadow-sm disabled:opacity-40"
                >
                  Înregistrează
                </button>
              </div>
            </div>
          </motion.div>
        ) : (
          <div className="flex items-center justify-between pt-2 border-t border-white/[0.05]">
            <span className="text-[11px] text-zinc-500">Loghează rapid nutriția</span>
            <button
              onClick={() => setShowQuick(true)}
              className="px-3 py-1 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-semibold text-emerald-400 hover:text-white transition-all inline-flex items-center gap-1"
            >
              <Plus className="w-3 h-3" /> Adaugă masă
            </button>
          </div>
        )}
      </AnimatePresence>
    </WidgetCard>
  )
}

