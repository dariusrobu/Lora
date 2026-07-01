import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchMoodMonthly, logMood } from "../../api/queries/mood"
import { WidgetCard } from "./WidgetCard"
import { Smile } from "lucide-react"
import { MOOD_EMOJI, MOOD_SCORE } from "../../api/constants/mood"

interface Props { onExpand?: () => void }

const QUICK_MOODS = ["great", "good", "okay", "meh", "bad"]

export function MoodWidget({ onExpand }: Props) {
  const qc = useQueryClient()

  const { data: entries, isLoading, isError, refetch } = useQuery({
    queryKey: ["mood", "monthly"],
    queryFn: fetchMoodMonthly,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const logMut = useMutation({
    mutationFn: logMood,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mood", "monthly"] }),
  })

  const recent = (entries ?? []).filter((e) => e.date).slice(-7)
  const today = recent.length > 0 ? recent[recent.length - 1] : null
  const avg = recent.length > 0
    ? recent.reduce((s, e) => s + (MOOD_SCORE[e.mood] ?? 3), 0) / recent.length
    : 0
  const hasData = recent.length > 0

  return (
    <WidgetCard
      icon={<Smile className="w-4 h-4" />}
      label="Mood"
      linkTo="/body?tab=mood"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="No mood data yet"
      emptyCTA={
        <div className="flex gap-1.5">
          {QUICK_MOODS.map((m) => (
            <motion.button key={m} onClick={() => logMut.mutate({ mood: m })}
              whileTap={{ scale: 0.85 }}
              className="w-9 h-9 rounded-full bg-white/10 dark:bg-white/[0.06] flex items-center justify-center text-lg hover:bg-white/20 dark:hover:bg-white/[0.1] transition-colors"
              title={m}>
              {MOOD_EMOJI[m] ?? "😐"}
            </motion.button>
          ))}
        </div>
      }
    >
      {/* Hero — today's mood */}
      <div className="flex items-center gap-3 mb-3">
        <motion.button
          whileTap={{ scale: 0.85 }}
          className="text-3xl">{MOOD_EMOJI[today?.mood ?? ""] ?? "😐"}</motion.button>
        <div className="text-xs space-y-0.5">
          <p className="text-text-primary font-medium capitalize">{today?.mood ?? "—"}</p>
          <p className="text-text-muted">Avg <span className="tabular-nums">{avg.toFixed(1)}</span> / 5 · {recent.length}d</p>
        </div>
      </div>

      {/* 7-day sparkline */}
      {recent.length > 0 && (
        <div className="flex items-end gap-1 h-7 mb-2">
          {recent.map((e, i) => {
            const score = MOOD_SCORE[e.mood] ?? 3
            const height = Math.max(16, score * 8)
            return (
              <div key={e.date ?? i} className="flex-1 flex flex-col items-center gap-0.5" title={`${e.date}: ${e.mood}`}>
                <div className="w-full rounded-full transition-all bg-violet-500"
                  style={{ height: `${height}%`, opacity: 0.3 + score * 0.14 }} />
              </div>
            )
          })}
        </div>
      )}

      {/* Quick mood buttons */}
      <div className="flex gap-1.5">
        {QUICK_MOODS.map((m) => (
          <motion.button key={m} onClick={() => logMut.mutate({ mood: m })}
            whileTap={{ scale: 0.85 }}
            className={`flex-1 py-1.5 rounded-xl text-center text-xs font-medium transition-all ${
              today?.mood === m
                ? "bg-pink-500 text-white"
                : "bg-white/10 dark:bg-white/[0.06] text-text-muted hover:text-text-primary hover:bg-white/20 dark:hover:bg-white/[0.1]"
            }`}>
            {MOOD_EMOJI[m]}
          </motion.button>
        ))}
      </div>
    </WidgetCard>
  )
}
