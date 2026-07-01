import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Apple, Soup, Utensils, Cookie, Plus } from "lucide-react"
import { Card, Button, Spinner } from "../components/ui"
import { fetchDailyNutrition, logMeal } from "../api/queries/nutrition"
import type { NutritionResponse, Meal } from "../types"

const mealIcons: Record<string, { icon: React.ElementType; label: string }> = {
  breakfast: { icon: Soup, label: "Breakfast" },
  lunch: { icon: Utensils, label: "Lunch" },
  dinner: { icon: Utensils, label: "Dinner" },
  snack: { icon: Cookie, label: "Snacks" },
}

const mealTypes = ["breakfast", "lunch", "dinner", "snack"]

function MacroBar({ label, current, target, unit, color }: { label: string; current: number; target: number; unit: string; color: string }) {
  const pct = Math.min(Math.round((current / target) * 100), 100)
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-text-secondary">{label}</span>
        <span className="font-bold text-text-primary">{current} <span className="font-normal text-text-muted">/ {target}{unit}</span></span>
      </div>
      <div className="h-1.5 bg-white/40 dark:bg-white/[0.06] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] text-text-muted">{pct}%</span>
    </div>
  )
}

function fmtDay(d: string) {
  return new Date(d + "T00:00:00").toLocaleDateString("en-US", { weekday: "short" })
}

export default function Nutrition() {
  const [modalOpen, setModalOpen] = useState(false)
  const [presetType, setPresetType] = useState("breakfast")
  const [description, setDescription] = useState("")
  const [calories, setCalories] = useState("")
  const [protein, setProtein] = useState("")
  const [carbs, setCarbs] = useState("")
  const [fat, setFat] = useState("")

  const qc = useQueryClient()

  const { data, isLoading } = useQuery<NutritionResponse>({
    queryKey: ["nutrition"],
    queryFn: fetchDailyNutrition,
  })

  const logMut = useMutation({
    mutationFn: logMeal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nutrition"] })
      setModalOpen(false)
      setDescription("")
      setCalories("")
      setProtein("")
      setCarbs("")
      setFat("")
    },
  })

  if (isLoading) return <Spinner className="py-12" />

  const { meals = [], totals = { calories: 0, protein: 0, carbs: 0, fat: 0 }, targets, weekHistory } = data ?? {}
  const t = targets ?? { calories: 2000, protein_g: 150, carbs_g: 200, fat_g: 70 }

  const grouped = meals.reduce<Record<string, Meal[]>>((acc, m) => {
    ;(acc[m.meal_type] ??= []).push(m)
    return acc
  }, {})

  const openModal = (type: string) => {
    setPresetType(type)
    setModalOpen(true)
  }

  const handleLog = () => {
    logMut.mutate({
      meal_type: presetType,
      description,
      calories: Number(calories),
      protein: protein ? Number(protein) : undefined,
      carbs: carbs ? Number(carbs) : undefined,
      fat: fat ? Number(fat) : undefined,
    })
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Nutrition</h1>
        <p className="text-text-secondary text-sm">Track your daily meals and macros</p>
      </div>

      {/* Macro progress bars */}
      <div className="glass-strong rounded-2xl p-4 shadow-apple-heavy">
        <p className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider mb-3">Today's Progress</p>
        <MacroBar label="Calories" current={totals.calories} target={t.calories} unit="kcal" color="bg-violet-500" />
        <MacroBar label="Protein" current={totals.protein} target={t.protein_g} unit="g" color="bg-violet-500" />
        <MacroBar label="Carbs" current={totals.carbs} target={t.carbs_g} unit="g" color="bg-violet-500" />
        <MacroBar label="Fat" current={totals.fat} target={t.fat_g} unit="g" color="bg-yellow-500" />
      </div>

      {/* Meals */}
      <div className="glass-strong rounded-2xl shadow-apple-heavy overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50">
          <h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Meals</h4>
        </div>
        <div className="divide-y divide-border/20">
          {mealTypes.map((type) => {
            const info = mealIcons[type]
            const Icon = info?.icon ?? Apple
            const typeMeals = grouped[type] ?? []

            return (
              <div key={type}>
                <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-white/[0.02] border border-transparent">
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 text-text-muted" />
                    <span className="text-sm font-medium text-text-primary w-16">{info?.label ?? type}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {typeMeals.length > 0 ? (
                      <span className="text-xs text-text-secondary">
                        {typeMeals.reduce((s, m) => s + m.calories, 0)}cal · P{typeMeals.reduce((s, m) => s + m.protein, 0)} · C{typeMeals.reduce((s, m) => s + m.carbs, 0)} · F{typeMeals.reduce((s, m) => s + m.fat, 0)}
                      </span>
                    ) : (
                      <span className="text-xs text-text-muted">—</span>
                    )}
                    <button
                      onClick={() => openModal(type)}
                      className="w-6 h-6 rounded-lg bg-surface border border-border text-text-muted hover:text-text-primary hover:bg-surface flex items-center justify-center transition-all"
                    >
                      <Plus className="w-3 h-3" />
                    </button>
                  </div>
                </div>
                {typeMeals.map((meal) => (
                  <div key={meal.id} className="ml-10 pl-3 border-l border-border py-1.5 mb-0.5">
                    <p className="text-xs text-text-primary">{meal.description}</p>
                    <p className="text-[10px] text-text-muted">
                      P{meal.protein}g · C{meal.carbs}g · F{meal.fat}g
                    </p>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      </div>

      {/* Targets card */}
      <div className="glass-strong rounded-2xl p-4 shadow-apple-heavy">
        <p className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider mb-3">Daily Targets</p>
        <div className="grid grid-cols-4 gap-3 text-sm">
          <div className="flex flex-col"><span className="text-apple-caption2 text-text-muted">Calories</span><span className="text-lg font-bold text-text-primary">{t.calories}</span></div>
          <div className="flex flex-col"><span className="text-apple-caption2 text-text-muted">Protein</span><span className="text-lg font-bold text-text-primary">{t.protein_g}g</span></div>
          <div className="flex flex-col"><span className="text-apple-caption2 text-text-muted">Carbs</span><span className="text-lg font-bold text-text-primary">{t.carbs_g}g</span></div>
          <div className="flex flex-col"><span className="text-apple-caption2 text-text-muted">Fat</span><span className="text-lg font-bold text-text-primary">{t.fat_g}g</span></div>
        </div>
      </div>

      {/* This Week */}
      {weekHistory && weekHistory.length > 0 && (
        <div className="glass-strong rounded-2xl shadow-apple-heavy overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50">
            <h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">This Week</h4>
          </div>
          <div className="divide-y divide-border/20">
            {weekHistory.map((day) => {
              const pct = Math.min(Math.round((day.calories / t.calories) * 100), 100)
              return (
                <div key={day.date} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="text-xs text-text-muted w-8 shrink-0">{fmtDay(day.date)}</span>
                  <div className="flex-1 h-1.5 bg-white/40 dark:bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-violet-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs text-text-secondary w-12 text-right tabular-nums">{day.calories}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Log Meal modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setModalOpen(false)}>
          <div className="bg-bg border border-border rounded-xl p-5 w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <p className="text-sm font-semibold text-text-primary mb-4">Log Meal</p>
            <div className="space-y-3">
              <select
                value={presetType}
                onChange={(e) => setPresetType(e.target.value)}
                className="w-full bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary outline-none focus:border-primary/30 transition-colors"
              >
                {mealTypes.map((t) => (
                  <option key={t} value={t} className="bg-bg">{mealIcons[t]?.label ?? t}</option>
                ))}
              </select>
              <input
                autoFocus
                placeholder="Description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  placeholder="Calories"
                  type="number"
                  value={calories}
                  onChange={(e) => setCalories(e.target.value)}
                  className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                />
                <input
                  placeholder="Protein (g)"
                  type="number"
                  value={protein}
                  onChange={(e) => setProtein(e.target.value)}
                  className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                />
                <input
                  placeholder="Carbs (g)"
                  type="number"
                  value={carbs}
                  onChange={(e) => setCarbs(e.target.value)}
                  className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                />
                <input
                  placeholder="Fat (g)"
                  type="number"
                  value={fat}
                  onChange={(e) => setFat(e.target.value)}
                  className="bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                />
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => setModalOpen(false)}
                  className="flex-1 py-2 rounded-lg text-xs font-medium text-text-secondary hover:text-text-primary border border-border transition-colors"
                >
                  Cancel
                </button>
                <Button
                  onClick={handleLog}
                  disabled={!description.trim() || logMut.isPending}
                  className="flex-1"
                >
                  {logMut.isPending ? <Spinner size="sm" /> : "Log"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  )
}
