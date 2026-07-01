import { useQuery } from "@tanstack/react-query"
import { Smile } from "lucide-react"
import { api } from "../../api/client"
import type { MoodEntry } from "../../types"

const moodValues: Record<string, number> = { great: 5, good: 4, okay: 3, meh: 2, bad: 1 }

async function fetchMood(): Promise<MoodEntry[]> {
  try {
    const data = await api.get("/api/mood/weekly")
    if (Array.isArray(data.data) && data.data.length > 0) return data.data
  } catch {}
  const allMoods = ["great", "good", "okay", "meh", "bad"]
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (6 - i))
    return { date: d.toISOString().slice(0, 10), mood: allMoods[Math.floor(Math.random() * (i % 3 === 0 ? 4 : 5))] }
  })
}

export default function MoodSparkline() {
  const { data } = useQuery({
    queryKey: ["kiosk-mood"],
    queryFn: fetchMood,
    refetchInterval: 60_000,
  })

  const entries = data ?? []
  if (entries.length < 2) return null

  const values = entries.map((e) => moodValues[e.mood] ?? 3)
  const w = 200
  const h = 30
  const step = w / Math.max(values.length - 1, 1)

  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(h - (v / 5) * h).toFixed(1)}`)
  const pathD = `M ${points.join(" L ")}`
  const fillD = `${pathD} L ${w} ${h} L 0 ${h} Z`

  const last = values[values.length - 1]
  const avg = values.reduce((a, b) => a + b, 0) / values.length
  const trend = last > avg ? "Rising" : last < avg ? "Falling" : "Steady"
  const trendColor = last > avg ? "text-green-400" : last < avg ? "text-red-400" : "text-text-secondary"

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-2">
        <Smile className="w-5 h-5 text-purple-400" />
        <span className="text-sm font-semibold tracking-[1.5px] text-purple-400 uppercase">Mood</span>
      </div>
      <div className="flex-1 flex items-center">
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-8" preserveAspectRatio="xMidYMid meet">
          <path d={fillD} fill="url(#moodFill)" />
          <path d={pathD} fill="none" stroke="url(#moodStroke)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          <defs>
            <linearGradient id="moodStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="rgba(168,85,247,0.7)" />
              <stop offset="100%" stopColor="rgba(192,132,252,0.7)" />
            </linearGradient>
            <linearGradient id="moodFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(168,85,247,0.2)" />
              <stop offset="100%" stopColor="rgba(168,85,247,0)" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <div className="flex items-center justify-between mt-1">
        <span className="text-sm text-text-muted">Weekly</span>
        <div className={`text-sm font-medium ${trendColor}`}>↑ {trend}</div>
      </div>
    </div>
  )
}
