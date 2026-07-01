import { useQuery } from "@tanstack/react-query"
import { Loader2, Calendar } from "lucide-react"
import { api } from "../../api/client"
import type { CalendarDay } from "../../types"

type TimelineItem = {
  id: number | string
  time: string
  endTime?: string
  title: string
  subtitle?: string
  type: "event" | "class"
}

async function fetchWeek(): Promise<CalendarDay[]> {
  try {
    const data = await api.get("/api/calendar/week")
    return data.data?.days ?? []
  } catch {
    return []
  }
}

const mockItems: TimelineItem[] = [
  { id: "m1", time: "09:00", title: "Team standup", type: "event" },
  { id: "m2", time: "11:00", title: "Design review", type: "event" },
  { id: "m3", time: "14:00", endTime: "16:00", title: "Machine Learning", subtitle: "Lecture", type: "class" },
  { id: "m4", time: "18:00", title: "Gym", type: "event" },
]

export default function TodaySchedule() {
  const { data: days, isLoading } = useQuery({
    queryKey: ["kiosk-schedule"],
    queryFn: fetchWeek,
    refetchInterval: 60_000,
  })

  const todayStr = new Date().toISOString().slice(0, 10)
  const dayData = days?.find((d: CalendarDay) => d.date === todayStr)

  const items: TimelineItem[] = dayData
    ? [
        ...(dayData.events ?? []).map((e) => ({
          id: `ev-${e.id}`,
          time: e.event_time ?? "00:00",
          title: e.title,
          type: "event" as const,
        })),
        ...(dayData.schedule ?? []).map((s) => ({
          id: `sch-${s.id}`,
          time: s.start_time,
          endTime: s.end_time,
          title: s.subject_name,
          subtitle: s.class_type,
          type: "class" as const,
        })),
      ].sort((a, b) => a.time.localeCompare(b.time))
    : mockItems

  const isPast = (time: string) => {
    const [h, m] = time.split(":").map(Number)
    const nowH = new Date().getHours()
    const nowM = new Date().getMinutes()
    return h < nowH || (h === nowH && m < nowM)
  }

  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin text-purple-400 mx-auto py-6" />

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Calendar className="w-6 h-6 text-purple-400" />
        <h3 className="text-lg font-semibold tracking-[1.5px] text-purple-400 uppercase">Today's Schedule</h3>
      </div>
      <div className="space-y-0">
        {items.length === 0 && <p className="text-xl text-text-muted text-center py-2">Nothing scheduled today</p>}
        {items.slice(0, 5).map((item, i) => {
          const past = isPast(item.time)
          return (
            <div key={item.id} className="flex gap-3">
              <div className="flex flex-col items-center w-6 shrink-0">
                <div className={`w-3 h-3 rounded-full mt-1.5 ${past ? "bg-purple-400/20" : "bg-purple-400"}`} />
                {i < Math.min(items.length, 5) - 1 && (
                  <div className={`w-px flex-1 min-h-[32px] ${past ? "bg-purple-400/[0.04]" : "bg-purple-400/[0.12]"}`} />
                )}
              </div>
              <div className={`pb-3 flex-1 min-w-0 ${past ? "opacity-25" : ""}`}>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-medium text-text-primary/60 tabular-nums">{item.time}</span>
                  {item.endTime && <span className="text-base text-text-muted">— {item.endTime}</span>}
                </div>
                <div className="text-xl text-text-primary/90 truncate">{item.title}</div>
                {item.subtitle && <div className="text-lg text-text-muted truncate">{item.subtitle}</div>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
