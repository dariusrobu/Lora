import { useQuery } from "@tanstack/react-query"
import { useState, useEffect } from "react"
import { Loader2 } from "lucide-react"
import { api } from "../../api/client"
import type { CalendarDay } from "../../types"

async function fetchWeek(): Promise<CalendarDay[]> {
  try {
    const res = await api.get("/api/calendar/week")
    return res.data?.days ?? []
  } catch {
    return []
  }
}

function getNextEvent(days: CalendarDay[]): { title: string; time: Date } | null {
  const now = new Date()
  for (const day of days) {
    for (const ev of day.events) {
      const dt = new Date(ev.event_date)
      if (isNaN(dt.getTime())) continue
      if (ev.event_time) {
        const [h, m] = ev.event_time.split(":").map(Number)
        if (!isNaN(h) && !isNaN(m)) dt.setHours(h, m, 0)
      }
      if (dt > now) return { title: ev.title, time: dt }
    }
    for (const s of day.schedule) {
      const dt = new Date(day.date)
      if (isNaN(dt.getTime())) continue
      const [h, m] = s.start_time.split(":").map(Number)
      if (!isNaN(h) && !isNaN(m)) dt.setHours(h, m, 0)
      if (dt > now) return { title: s.subject_name, time: dt }
    }
  }
  return null
}

function fmtCountdown(ms: number) {
  if (isNaN(ms) || ms < 0) return "—"
  const h = Math.floor(ms / 3600000)
  const m = Math.floor((ms % 3600000) / 60000)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function EventsWidget() {
  const { data: days, isLoading } = useQuery({
    queryKey: ["kiosk-events"],
    queryFn: fetchWeek,
    refetchInterval: 60_000,
  })

  const next = days ? getNextEvent(days) : null
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="w-5 h-5 animate-spin text-white/20" /></div>
  }

  if (!next) return <p className="text-sm text-white/30 text-center self-center mt-4">No upcoming events</p>

  const diff = Math.max(0, next.time.getTime() - now)

  return (
    <div className="flex flex-col h-full">
      <div className="text-xs text-white/50 truncate">{next.title}</div>
      <div className="text-3xl font-light text-white text-glow mt-1">
        {fmtCountdown(diff)}
      </div>
      <div className="text-[10px] text-white/30 mt-auto">until next event</div>
    </div>
  )
}
