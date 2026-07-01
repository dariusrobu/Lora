import { useQuery } from "@tanstack/react-query"
import { Loader2, Target } from "lucide-react"
import { api } from "../../api/client"
import AnimatedNumber from "./AnimatedNumber"
import type { Goal } from "../../types"

async function fetchGoals(): Promise<Goal[]> {
  try {
    const data = await api.get("/api/goals")
    if (Array.isArray(data.data)) return data.data
    return []
  } catch {
    return [
      { id: 1, title: "Learn TypeScript", progress: 75, status: "active", time_horizon: "medium", tasks: [] },
      { id: 2, title: "Run 100km", progress: 45, status: "active", time_horizon: "long", tasks: [] },
    ]
  }
}

export default function GoalsWidget() {
  const { data: goals, isLoading } = useQuery({
    queryKey: ["kiosk-goals"],
    queryFn: fetchGoals,
    refetchInterval: 60_000,
  })

  const active = (goals ?? []).filter((g: Goal) => g.status === "active").slice(0, 2)
  const avg = active.length > 0 ? Math.round(active.reduce((s: number, g: Goal) => s + g.progress, 0) / active.length) : 0

  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin text-emerald-400 mx-auto mt-6" />

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-2">
        <Target className="w-5 h-5 text-emerald-400" />
        <span className="text-sm font-semibold tracking-[1.5px] text-emerald-400 uppercase">Goals</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-5xl font-light text-text-primary">
          <AnimatedNumber value={avg} />
        </span>
        <span className="text-sm text-text-secondary">avg done</span>
      </div>
      <div className="mt-3 space-y-2 flex-1 min-h-0 overflow-auto">
        {active.length === 0 && <p className="text-sm text-text-muted">No active goals</p>}
        {active.map((g: Goal) => (
          <div key={g.id}>
            <div className="flex justify-between text-sm mb-0.5">
              <span className="text-text-secondary truncate mr-2">{g.title}</span>
              <span className="text-text-muted shrink-0 tabular-nums">{g.progress}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-text-muted/20 overflow-hidden">
              <div
                className="h-full rounded-full bg-emerald-400/60 transition-all duration-500"
                style={{ width: `${g.progress}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
