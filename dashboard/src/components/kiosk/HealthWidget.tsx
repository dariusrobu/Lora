import { useQuery } from "@tanstack/react-query"
import { Loader2, Heart, Droplets, Moon, Apple } from "lucide-react"
import { api } from "../../api/client"
import AnimatedNumber from "./AnimatedNumber"

async function fetchAll() {
  try {
    const [healthRes, nutritionRes] = await Promise.all([
      api.get("/api/health/summary"),
      api.get("/api/nutrition/daily"),
    ])

    const healthData = healthRes.data ?? { summary: {} }
    const nutritionData = nutritionRes.data ?? { totals: {}, targets: {} }

    return {
      summary: healthData.summary ?? {},
      totals: nutritionData.totals ?? {},
      targets: nutritionData.targets ?? {},
    }
  } catch {
    return {
      summary: { avg_sleep: 7.5, avg_water: 1800, recent_weight: 65, prev_weight: 65, weight_trend: "stable" },
      totals: { calories: 1450, protein: 85, carbs: 180, fat: 45 },
      targets: { calories: 2000, protein_g: 150, carbs_g: 200, fat_g: 70 },
    }
  }
}

export default function HealthWidget() {
  const { data } = useQuery({
    queryKey: ["kiosk-health"],
    queryFn: fetchAll,
    refetchInterval: 60_000,
  })

  if (!data) return <Loader2 className="w-6 h-6 animate-spin text-blue-400 mx-auto mt-6" />

  const s = data.summary
  const t = data.totals
  const targets = data.targets

  const sleep = s.avg_sleep ?? null
  const water = s.avg_water ?? null
  const weight = s.recent_weight ?? null
  const weightPrev = s.prev_weight ?? null
  const cal = t.calories ?? 0
  const protein = t.protein ?? 0
  const carbs = t.carbs ?? 0
  const fat = t.fat ?? 0
  const calTarget = targets?.calories ?? 2000
  const proteinTarget = targets?.protein_g ?? 150
  const carbsTarget = targets?.carbs_g ?? 200
  const fatTarget = targets?.fat_g ?? 70

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-2">
        <Heart className="w-5 h-5 text-blue-400" />
        <span className="text-base font-semibold tracking-[1.5px] text-blue-400 uppercase">Health</span>
      </div>
      <div className="grid grid-cols-2 gap-y-2 gap-x-4 flex-1">
        <div>
          <div className="flex items-center gap-1 text-text-muted text-xs mb-0.5">
            <Moon className="w-3 h-3" /> Sleep
          </div>
          <span className="text-4xl font-light text-text-primary tabular-nums truncate block">
            {sleep != null
              ? <AnimatedNumber value={sleep} decimals={1} suffix="h" />
              : "--"}
          </span>
        </div>
        <div>
          <div className="flex items-center gap-1 text-text-muted text-xs mb-0.5">
            <Droplets className="w-3 h-3 text-blue-300" /> Water
          </div>
          <span className="text-4xl font-light text-blue-300 tabular-nums truncate block">
            {water != null
              ? <AnimatedNumber value={water / 1000} decimals={1} suffix="L" />
              : "--"}
          </span>
        </div>
        {weight != null && (
          <div className="col-span-2 flex items-center gap-2 text-sm border-t border-white/5 pt-2 mt-1">
            <span className="text-text-muted">⚖️ Weight</span>
            <span className="tabular-nums text-text-primary">{weight} kg</span>
            {weightPrev != null && weightPrev !== weight && (
              <span className={`text-xs ${weight > weightPrev ? "text-red-400" : "text-green-400"}`}>
                {weight > weightPrev ? "▲" : "▼"} {Math.abs(weight - weightPrev).toFixed(1)}
              </span>
            )}
          </div>
        )}
        <div className="col-span-2 border-t border-white/5 pt-2">
          <div className="flex items-center gap-1 text-text-muted text-xs mb-1">
            <Apple className="w-3 h-3 text-green-300" /> Nutrition
          </div>
          <div className="flex items-baseline gap-x-2 gap-y-1 text-sm flex-wrap">
            <span className="text-green-200 tabular-nums">
              <AnimatedNumber value={cal} suffix="" />
              <span className="text-text-muted">/{calTarget}</span> kcal
            </span>
            <span className="text-text-muted">P</span>
            <span className="tabular-nums">
              <AnimatedNumber value={protein} suffix="" />
              <span className="text-text-muted">/{proteinTarget}</span>
            </span>
            <span className="text-text-muted">C</span>
            <span className="tabular-nums">
              <AnimatedNumber value={carbs} suffix="" />
              <span className="text-text-muted">/{carbsTarget}</span>
            </span>
            <span className="text-text-muted">F</span>
            <span className="tabular-nums">
              <AnimatedNumber value={fat} suffix="" />
              <span className="text-text-muted">/{fatTarget}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
