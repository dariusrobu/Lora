import { Moon, Droplets, Scale, Cigarette, TrendingUp, TrendingDown, Minus } from "lucide-react"
import { GlassCard } from "./GlassCard"

interface HealthLog {
  log_date: string
  sleep_hours: number | null
  water_ml: number | null
  weight_kg: number | null
  cigarettes: number | null
}

interface HealthCardProps {
  logs: HealthLog[]
  onClick?: () => void
}

export function HealthCard({ logs, onClick }: HealthCardProps) {
  const latest = logs[0] || {}
  const prev = logs[1] || {}

  const getTrend = (curr: number | null, p: number | null) => {
    if (curr === null || p === null) return <Minus className="w-3 h-3 text-text-muted" />
    if (curr > p) return <TrendingUp className="w-3 h-3 text-text-secondary" />
    if (curr < p) return <TrendingDown className="w-3 h-3 text-text-secondary" />
    return <Minus className="w-3 h-3 text-text-muted" />
  }

  return (
    <GlassCard className="group relative overflow-hidden" onClick={onClick}>
      <div className="flex justify-between items-start mb-6">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">Status Vital</h3>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center">
              <Moon className="w-4 h-4 text-text-secondary" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-text-secondary uppercase tracking-tighter">Somn</p>
              <div className="flex items-center gap-2">
                <p className="text-xl font-black text-text-primary">{latest.sleep_hours ?? "—"}<span className="text-[10px] opacity-30 ml-1">h</span></p>
                {getTrend(latest.sleep_hours, prev.sleep_hours)}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center">
              <Droplets className="w-4 h-4 text-text-secondary" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-text-secondary uppercase tracking-tighter">Apă</p>
              <div className="flex items-center gap-2">
                <p className="text-xl font-black text-text-primary">{latest.water_ml ?? 0}<span className="text-[10px] opacity-30 ml-1">ml</span></p>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center">
              <Scale className="w-4 h-4 text-text-secondary" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-text-secondary uppercase tracking-tighter">Greutate</p>
              <div className="flex items-center gap-2">
                <p className="text-xl font-black text-text-primary">{latest.weight_kg ?? "—"}<span className="text-[10px] opacity-30 ml-1">kg</span></p>
                {getTrend(latest.weight_kg, prev.weight_kg)}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center">
              <Cigarette className="w-4 h-4 text-text-secondary" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-text-secondary uppercase tracking-tighter">Țigări</p>
              <div className="flex items-center gap-2">
                <p className="text-xl font-black text-text-primary">{latest.cigarettes ?? 0}</p>
                {getTrend(latest.cigarettes, prev.cigarettes)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </GlassCard>
  )
}
