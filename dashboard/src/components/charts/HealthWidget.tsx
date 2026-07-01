import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchHealthSummary, logHealth } from "../../api/queries/health"
import { WidgetCard } from "./WidgetCard"
import { Heart, Plus, Minus } from "lucide-react"

interface Props { onExpand?: () => void }

export function HealthWidget({ onExpand }: Props) {
  const qc = useQueryClient()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["health-summary"],
    queryFn: fetchHealthSummary,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const logMut = useMutation({
    mutationFn: logHealth,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["health-summary"] }),
  })

  const today = data?.history?.[0]
  const sleep = today?.sleep_hours
  const water = today?.water_ml
  const cigs = today?.cigarettes
  const hasData = data?.history && data.history.length > 0

  const sleepPct = sleep ? Math.min(Math.round((sleep / 8) * 100), 100) : 0
  const waterPct = water ? Math.min(Math.round((water / 2500) * 100), 100) : 0

  const quickSleep = (delta: number) => {
    const current = today?.sleep_hours ?? 0
    logMut.mutate({ sleep_hours: Math.max(0, Math.min(12, current + delta)) })
  }
  const quickWater = (ml: number) => {
    const current = today?.water_ml ?? 0
    logMut.mutate({ water_ml: current + ml })
  }
  const toggleCig = () => {
    logMut.mutate({ cigarettes: (today?.cigarettes ?? 0) + 1 })
  }

  return (
    <WidgetCard
      icon={<Heart className="w-4 h-4" />}
      label="Health"
      linkTo="/health"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="No health data yet"
      emptyCTA={
        <motion.div whileTap={{ scale: 0.97 }}>
          <button onClick={() => logMut.mutate({})}
            className="inline-block px-4 py-1.5 rounded-full glass-strong text-apple-caption2 font-medium text-primary">
            Log today
          </button>
        </motion.div>
      }
    >
      {/* Sleep ring + Water ring */}
      <div className="flex items-center gap-4 mb-3">
        {/* Sleep */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-text-muted">Sleep</span>
            <span className="text-xs font-semibold text-text-primary tabular-nums">{sleep ?? "-"}h</span>
          </div>
          <div className="h-2 bg-white/40 dark:bg-white/[0.06] rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500"
              style={{ width: `${sleepPct}%`, background: "linear-gradient(90deg, #6366f1, #7c3aed)" }} />
          </div>
          <div className="flex gap-1 mt-1.5">
            <button onClick={() => quickSleep(-0.5)} disabled={logMut.isPending}
              className="w-6 h-6 rounded-full bg-white/10 dark:bg-white/[0.06] flex items-center justify-center text-text-muted hover:text-text-primary transition-colors">
              <Minus className="w-3 h-3" />
            </button>
            <button onClick={() => quickSleep(0.5)} disabled={logMut.isPending}
              className="w-6 h-6 rounded-full bg-white/10 dark:bg-white/[0.06] flex items-center justify-center text-text-muted hover:text-text-primary transition-colors">
              <Plus className="w-3 h-3" />
            </button>
          </div>
        </div>
        {/* Water */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-text-muted">Water</span>
            <span className="text-xs font-semibold text-sky-500 tabular-nums">{water ?? "-"}ml</span>
          </div>
          <div className="h-2 bg-white/40 dark:bg-white/[0.06] rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500"
              style={{ width: `${waterPct}%`, background: "linear-gradient(90deg, #0ea5e9, #38bdf8)" }} />
          </div>
          <div className="flex gap-1 mt-1.5">
            <button onClick={() => quickWater(250)} disabled={logMut.isPending}
              className="w-6 h-6 rounded-full bg-white/10 dark:bg-white/[0.06] flex items-center justify-center text-text-muted hover:text-text-primary transition-colors">
              <Plus className="w-3 h-3" />
            </button>
            <button onClick={() => quickWater(500)} disabled={logMut.isPending}
              className="px-2 h-6 rounded-full bg-white/10 dark:bg-white/[0.06] text-[9px] text-text-muted hover:text-text-primary transition-colors font-medium">
              +500
            </button>
          </div>
        </div>
      </div>

      {/* Cigarettes quick-toggle */}
      <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-white/10 dark:bg-white/[0.04]">
        <div className="flex items-center gap-2">
          <span className="text-sm">🚬</span>
          <span className="text-xs text-text-muted">Today:</span>
          <span className="text-sm font-bold text-text-primary tabular-nums">{cigs ?? 0}</span>
        </div>
        <motion.button onClick={toggleCig} disabled={logMut.isPending}
          whileTap={{ scale: 0.9 }}
          className="px-3 py-1 rounded-full bg-red-500/10 text-red-500 text-[10px] font-medium hover:bg-red-500/20 transition-colors">
          +1
        </motion.button>
      </div>
    </WidgetCard>
  )
}
