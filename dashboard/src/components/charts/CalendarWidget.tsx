import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { twMerge } from "tailwind-merge"
import { fetchWeek } from "../../api/queries/calendar"
import { Card } from "../ui/Card"
import { Spinner } from "../ui/Spinner"
import { ArrowRight, Maximize2, CalendarDays } from "lucide-react"

const dayLabels = ["L", "M", "M", "J", "V", "S", "D"]

interface Props {
  onExpand?: () => void
}

export function CalendarWidget({ onExpand }: Props) {
  const { data: week, isLoading } = useQuery({
    queryKey: ["calendar", "dashboard"],
    queryFn: () => fetchWeek(new Date()),
    refetchInterval: 60_000,
  })

  const now = new Date()
  const todayStr = now.toISOString().slice(0, 10)
  const today = week?.find((d) => d.date === todayStr)
  const todayDow = now.getDay()
  const mondayOffset = todayDow === 0 ? -6 : 1 - todayDow
  const monday = new Date(now)
  monday.setDate(monday.getDate() + mondayOffset)

  const weekDates: Date[] = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday)
    d.setDate(d.getDate() + i)
    weekDates.push(d)
  }

  const hasEvents = today ? today.events.length > 0 : false
  const hasSchedule = today ? today.schedule.length > 0 : false
  const hasAnything = hasEvents || hasSchedule

  return (
    <Card liquid hover>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-widest">Calendar</h3>
        <div className="flex items-center gap-1">
          {onExpand && (
            <motion.button
              onClick={onExpand}
              whileTap={{ scale: 0.9 }}
              className="p-1.5 rounded-full text-text-muted hover:text-text-primary hover:bg-white/10 dark:hover:bg-white/[0.08] transition-colors"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </motion.button>
          )}
          <Link to="/calendar" className="p-1.5 rounded-full text-text-muted hover:text-text-primary hover:bg-white/10 dark:hover:bg-white/[0.08] transition-colors">
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
      <div className="md:hidden text-xs text-text-secondary font-medium mb-3">
        {todayStr ? new Date(todayStr + "T12:00:00").toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" }) : ""}
      </div>
      <div className="hidden md:grid grid-cols-7 gap-1 mb-4">
        {dayLabels.map((label, i) => {
          const d = weekDates[i]
          const dateStr = d.toISOString().slice(0, 10)
          const isToday = dateStr === todayStr
          const dayData = week?.find((wd) => wd.date === dateStr)
          const hasDayEvents = (dayData?.events.length ?? 0) > 0 || (dayData?.schedule.length ?? 0) > 0
          return (
            <div key={i} className="flex flex-col items-center gap-0.5">
              <span className="text-[10px] text-text-muted font-medium">{label}</span>
              <div
                className={twMerge(
                  "w-8 h-8 rounded-full flex items-center justify-center text-sm transition-colors",
                  isToday
                    ? "bg-rose-500 text-white font-bold shadow-sm"
                    : "text-text-secondary hover:bg-white/10 dark:hover:bg-white/[0.08]",
                )}
              >
                {d.getDate()}
              </div>
              {hasDayEvents && !isToday && <div className="w-1 h-1 rounded-full bg-text-muted" />}
              {isToday && <div className="w-1 h-1 rounded-full bg-accent" />}
            </div>
          )
        })}
      </div>
      {isLoading ? (
        <Spinner className="py-4" />
      ) : hasAnything ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2 max-h-[200px] overflow-y-auto">
          {hasEvents && (
            <div className="bg-white/60 dark:bg-white/[0.04] rounded-xl divide-y divide-border shadow-sm">
              <div className="px-3 py-1.5">
                <span className="text-apple-caption2 font-semibold text-text-muted uppercase tracking-wider">Events</span>
              </div>
              {today!.events.map((ev, idx) => (
                <div
                  key={ev.id}
                  className={`flex items-center gap-2.5 px-3 py-2 ${idx === today!.events.length - 1 && !hasSchedule ? "" : ""}`}
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                  {ev.event_time && (
                    <span className="text-apple-caption1 text-text-muted shrink-0 font-medium tabular-nums w-10">{ev.event_time}</span>
                  )}
                  <span className="text-apple-caption1 text-text-primary truncate">{ev.title}</span>
                  {ev.event_type === "reminder" && (
                    <span className="text-apple-caption2 text-text-muted shrink-0">reminder</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {hasSchedule && (
            <div className="bg-white/60 dark:bg-white/[0.04] rounded-xl divide-y divide-border shadow-sm">
              <div className="px-3 py-1.5">
                <span className="text-apple-caption2 font-semibold text-text-muted uppercase tracking-wider">Schedule</span>
              </div>
              {today!.schedule.map((s, idx) => (
                <div
                  key={s.id}
                  className={`flex items-center gap-2.5 px-3 py-2 ${idx === today!.schedule.length - 1 ? "" : ""}`}
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                  {s.start_time && (
                    <span className="text-apple-caption1 text-text-muted shrink-0 font-medium tabular-nums w-10">
                      {s.start_time.slice(0, 5)}
                    </span>
                  )}
                  <span className="text-apple-caption1 text-text-primary truncate">{s.subject_name}</span>
                  {s.room && <span className="text-apple-caption2 text-text-muted shrink-0">{s.room}</span>}
                </div>
              ))}
            </div>
          )}
        </motion.div>
      ) : (
        <div className="flex flex-col items-center py-4 text-center">
          <CalendarDays className="w-8 h-8 text-text-muted mb-2" />
          <p className="text-apple-caption1 text-text-muted mb-3">Nothing scheduled today</p>
          <motion.div whileTap={{ scale: 0.97 }}>
            <Link
              to="/calendar"
              className="inline-block px-4 py-1.5 rounded-full glass-strong text-apple-caption2 font-medium text-primary hover:bg-primary/10 transition-all"
            >
              Add event
            </Link>
          </motion.div>
        </div>
      )}
    </Card>
  )
}
