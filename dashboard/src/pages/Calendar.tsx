import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { fetchWeek, createEvent, deleteEvent } from "../api/queries/calendar"
import { Card, Button, Spinner } from "../components/ui"
import {
  ChevronLeft, ChevronRight, Plus, Trash2, CalendarDays, Clock, MapPin, GraduationCap,
} from "lucide-react"
import type { CalendarDay, CalendarEvent, CalendarScheduleEntry } from "../types"

function getMonday(d: Date): Date {
  const m = new Date(d)
  m.setDate(m.getDate() - ((m.getDay() + 6) % 7))
  m.setHours(0, 0, 0, 0)
  return m
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

function fmt(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

function fmtShort(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function fmtWeekRange(monday: Date): string {
  const sun = addDays(monday, 6)
  const sameMonth = monday.getMonth() === sun.getMonth()
  if (sameMonth) {
    return `${monday.toLocaleDateString("en-US", { month: "short" })} ${monday.getDate()} — ${sun.getDate()}, ${monday.getFullYear()}`
  }
  return `${fmtShort(monday)} — ${fmtShort(sun)}`
}

function isToday(d: Date): boolean {
  const t = new Date()
  return d.getDate() === t.getDate() && d.getMonth() === t.getMonth() && d.getFullYear() === t.getFullYear()
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getDate() === b.getDate() && a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()
}

export default function Calendar() {
  const [weekStart, setWeekStart] = useState<Date>(() => getMonday(new Date()))
  const [selectedIdx, setSelectedIdx] = useState<number>(() => {
    const today = new Date()
    const m = getMonday(today)
    return Math.min(Math.max(Math.round((today.getTime() - m.getTime()) / 86400000), 0), 6)
  })
  const [showAdd, setShowAdd] = useState(false)
  const [addTitle, setAddTitle] = useState("")
  const [addTime, setAddTime] = useState("")
  const [addDesc, setAddDesc] = useState("")

  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: ["calendar"] })

  const { data: days, isLoading } = useQuery({
    queryKey: ["calendar", weekStart.toISOString()],
    queryFn: () => fetchWeek(weekStart),
  })

  const createMut = useMutation({
    mutationFn: createEvent,
    onSuccess: () => {
      invalidate()
      setShowAdd(false)
      setAddTitle("")
      setAddTime("")
      setAddDesc("")
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteEvent,
    onSuccess: invalidate,
  })

  const selectedDay: CalendarDay | undefined = days?.[selectedIdx]

  const goBack = () => setWeekStart(addDays(weekStart, -7))
  const goForward = () => setWeekStart(addDays(weekStart, 7))
  const goToday = () => {
    const m = getMonday(new Date())
    setWeekStart(m)
    const today = new Date()
    setSelectedIdx(Math.min(Math.max(Math.round((today.getTime() - m.getTime()) / 86400000), 0), 6))
  }

  const handleAdd = () => {
    if (!addTitle.trim() || !selectedDay) return
    createMut.mutate({
      title: addTitle.trim(),
      date: selectedDay.date,
      time: addTime.trim() || undefined,
      description: addDesc.trim() || undefined,
    })
  }

  const weekDays = useMemo(() => {
    if (!weekStart) return []
    return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
  }, [weekStart])

  if (isLoading) return <Spinner className="py-12" />

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Calendar</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={goToday}
            className="text-xs text-primary hover:text-primary-light bg-primary/10 px-2.5 py-1.5 rounded-lg transition-colors"
          >
            Today
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1 text-xs bg-primary/15 text-primary hover:bg-primary/25 px-2.5 py-1.5 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> Event
          </button>
        </div>
      </div>

      {/* Week navigation */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={goBack} className="text-text-muted hover:text-text-primary transition-colors">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <span className="text-sm font-medium text-text-primary flex-1 text-center">
          {fmtWeekRange(weekStart)}
        </span>
        <button onClick={goForward} className="text-text-muted hover:text-text-primary transition-colors">
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* Day chips */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-1 -mx-1 px-1">
        {weekDays.map((d, i) => {
          const day = days?.[i]
          const eventCount = (day?.events?.length ?? 0) + (day?.schedule?.length ?? 0)
          const isSel = selectedIdx === i
          const isT = isToday(d)
          return (
            <button
              key={i}
              onClick={() => setSelectedIdx(i)}
              className={`flex flex-col items-center min-w-[52px] py-2 px-2 rounded-xl text-xs transition-all shrink-0 ${
                isSel
                  ? "bg-primary/20 text-primary border border-primary/20"
                  : isT
                    ? "bg-surface text-text-primary border border-border"
                    : "text-text-muted hover:text-text-secondary hover:bg-surface border border-transparent"
              }`}
            >
              <span className="text-[10px] uppercase tracking-wider">{d.toLocaleDateString("en-US", { weekday: "short" })}</span>
              <span className={`text-sm font-semibold mt-0.5 ${isT ? "text-primary" : ""}`}>{d.getDate()}</span>
              {eventCount > 0 && (
                <span className={`mt-0.5 w-1.5 h-1.5 rounded-full ${isSel ? "bg-primary" : "bg-surface"}`} />
              )}
            </button>
          )
        })}
      </div>

      {/* Add event form */}
      <AnimatePresence>
        {showAdd && selectedDay && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden mb-4"
          >
            <Card className="p-3 space-y-2">
              <div className="text-xs font-medium text-text-primary">
                Add event for {selectedDay.day_name}, {fmt(new Date(selectedDay.date))}
              </div>
              <input
                value={addTitle}
                onChange={(e) => setAddTitle(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleAdd() }}
                placeholder="Event title..."
                className="w-full bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                autoFocus
              />
              <div className="flex gap-2">
                <input
                  value={addTime}
                  onChange={(e) => setAddTime(e.target.value)}
                  placeholder="Time (optional)"
                  type="time"
                  className="w-32 bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors [color-scheme:dark]"
                />
                <input
                  value={addDesc}
                  onChange={(e) => setAddDesc(e.target.value)}
                  placeholder="Description (optional)"
                  className="flex-1 bg-surface border border-border rounded-lg py-2 px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setShowAdd(false); setAddTitle(""); setAddTime(""); setAddDesc("") }}
                  className="text-xs text-text-muted hover:text-text-secondary px-3 py-1.5 transition-colors"
                >
                  Cancel
                </button>
                <Button
                  size="sm"
                  onClick={handleAdd}
                  disabled={!addTitle.trim() || createMut.isPending}
                >
                  {createMut.isPending ? <Spinner size="sm" /> : "Add Event"}
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Selected day events */}
      {selectedDay && (
        <div className="space-y-3">
          {selectedDay.events.length === 0 && selectedDay.schedule.length === 0 ? (
            <Card><p className="text-sm text-text-muted text-center py-8">No events on this day</p></Card>
          ) : (
            <>
              {/* Events */}
              {selectedDay.events.length > 0 && (
                <div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">Events</div>
                  <div className="space-y-1">
                    {selectedDay.events.map((ev: CalendarEvent) => (
                      <Card key={ev.id} className="flex items-center gap-3 py-2.5 px-3 group">
                        <CalendarDays className="w-4 h-4 text-primary shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-white font-medium">{ev.title}</span>
                            {ev.event_type === "reminder" && (
                              <span className="text-[10px] text-amber-400 bg-amber-500/15 px-1.5 py-0.5 rounded">Reminder</span>
                            )}
                          </div>
                          {ev.description && (
                            <p className="text-xs text-text-muted">{ev.description}</p>
                          )}
                        </div>
                        {ev.event_time && (
                          <span className="text-xs text-text-secondary flex items-center gap-1 shrink-0">
                            <Clock className="w-3 h-3" /> {ev.event_time}
                          </span>
                        )}
                        <button
                          onClick={() => deleteMut.mutate(ev.id)}
                          className="text-text-muted hover:text-red-500 transition-colors shrink-0 opacity-0 group-hover:opacity-100"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* Schedule */}
              {selectedDay.schedule.length > 0 && (
                <div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2 flex items-center gap-1">
                    <GraduationCap className="w-3 h-3" /> Schedule
                  </div>
                  <div className="space-y-1">
                    {selectedDay.schedule.map((s: CalendarScheduleEntry) => (
                      <Card key={s.id} className="flex items-center gap-3 py-2.5 px-3 opacity-70">
                        <GraduationCap className="w-4 h-4 text-emerald-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm text-text-primary">{s.subject_name}</span>
                          {s.class_type && (
                            <span className="text-[10px] text-text-muted ml-2">{s.class_type}</span>
                          )}
                        </div>
                        <span className="text-xs text-text-muted flex items-center gap-1 shrink-0">
                          <Clock className="w-3 h-3" /> {s.start_time?.slice(0, 5)}
                        </span>
                        {s.room && (
                          <span className="text-xs text-text-muted flex items-center gap-1 shrink-0">
                            <MapPin className="w-3 h-3" /> {s.room}
                          </span>
                        )}
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
