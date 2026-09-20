import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState, useEffect, useRef, useCallback } from "react"
import { api } from "../../api/client"
import type { Task, CalendarDay } from "../../types"
import { useLoraLive } from "../../hooks/useLoraLive"
import { fetchWeather } from "../../api/queries/weather"


const priorityRank: Record<string, number> = { high: 0, medium: 1, low: 2, normal: 3 }

function DateSection() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  const days = ["Du", "Lu", "Ma", "Mi", "Jo", "Vi", "Sâ"]
  const months = ["Ian", "Feb", "Mar", "Apr", "Mai", "Iun", "Iul", "Aug", "Sep", "Oct", "Noi", "Dec"]
  const h = String(now.getHours()).padStart(2, "0")
  const m = String(now.getMinutes()).padStart(2, "0")
  const s = String(now.getSeconds()).padStart(2, "0")
  return (
    <>
      <div className="opacity-80">{days[now.getDay()]}, {now.getDate()} {months[now.getMonth()]} {now.getFullYear()}</div>
      <div className="text-xl font-light tracking-widest opacity-90 tabular-nums mt-0.5">{h}:{m}:{s}</div>
    </>
  )
}

function WeatherSection() {
  const { data } = useQuery({
    queryKey: ["terminal-weather"],
    queryFn: () => fetchWeather(44.43, 26.10),
    refetchInterval: 60_000,
    retry: 1,
  })
  const w = data?.current ?? null
  if (!w) return <div className="opacity-40">—</div>

  const emoji = (c?: string) => {
    const s = (c ?? "").toLowerCase()
    if (s.includes("rain") || s.includes("ploaie")) return "🌧"
    if (s.includes("cloud") || s.includes("nor")) return "☁️"
    if (s.includes("snow") || s.includes("zăpadă")) return "❄️"
    if (s.includes("thunder") || s.includes("furtună")) return "⛈"
    if (s.includes("fog") || s.includes("ceață")) return "🌫"
    if (s.includes("clear") || s.includes("senin")) return "☀️"
    return "🌤"
  }

  return (
    <>
      <div>
        {emoji(w.condition)} {Math.round(w.temp ?? w.temperature ?? 0)}°C{" "}
        <span className="opacity-40">{w.condition ?? ""}</span>
      </div>
      <div className="opacity-50 text-xs">
        H:{Math.round(w.temp_max ?? 0)}° L:{Math.round(w.temp_min ?? 0)}°
      </div>
    </>
  )
}

function TasksSection() {
  const { data: tasks } = useQuery({
    queryKey: ["terminal-tasks"],
    queryFn: async () => {
      const d = await api.get("/api/tasks")
      if (Array.isArray(d.data?.tasks)) return d.data.tasks as Task[]
      return (d.data ?? []) as Task[]
    },
    refetchInterval: 60_000,
  })
  const pending = (tasks ?? []).filter(t => t.status === "pending")
  const sorted = [...pending].sort((a, b) => {
    const ra = priorityRank[a.priority] ?? 3
    const rb = priorityRank[b.priority] ?? 3
    return ra - rb
  })

  if (sorted.length === 0) return <div className="opacity-40">—</div>

  return (
    <>
      <div><span className="opacity-80">{sorted.length} pending</span></div>
      {sorted.map((t) => (
        <div key={t.id} className="flex items-center gap-1.5 opacity-70">
          <span className={`w-3 text-center shrink-0 ${t.priority === "high" ? "opacity-80 font-bold" : "opacity-30"}`}>
            {t.priority === "high" ? "!" : "○"}
          </span>
          <span className="truncate">{t.title}</span>
        </div>
      ))}
    </>
  )
}

function ServerSection() {
  const { data } = useQuery({
    queryKey: ["kiosk-server"],
    queryFn: async () => {
      const d = await api.get("/api/homeserver/status")
      return d.data as { services: { name: string; port: number; icon: string; up: boolean }[]; system: { cpu_usage: number; ram_used_mb: number; ram_total_mb: number; ram_used_pct: number; ssd: { used_pct: number }; hdd: { used_pct: number } }; downloads: unknown[] }
    },
    refetchInterval: 30_000,
  })

  if (!data) return <div className="opacity-40">fetching...</div>

  const s = data.system
  const svc = data.services ?? []
  const upCount = svc.filter(s => s.up).length

  return (
    <>
      <div className="opacity-70">
        <span className="opacity-50">{upCount}/{svc.length}</span> services up
      </div>
      <div className="opacity-70">
        CPU {s.cpu_usage}%  RAM {s.ram_used_pct}%  SSD {s.ssd?.used_pct ?? 0}%  HDD {s.hdd?.used_pct ?? 0}%
      </div>
      <div className="opacity-50 text-xs truncate">
        {svc.map(s => s.up ? "●" : "○").join(" ")}
      </div>
    </>
  )
}

function EventsSection() {
  const { data } = useQuery({
    queryKey: ["terminal-events"],
    queryFn: async () => {
      const d = await api.get("/api/calendar/week")
      return (d.data?.days ?? []) as CalendarDay[]
    },
    refetchInterval: 60_000,
  })

  const now = new Date()
  const upcoming: { title: string; time: string }[] = []
  if (data && data.length > 0) {
    for (const day of data) {
      for (const ev of day.events ?? []) {
        const dt = new Date(ev.event_date)
        if (isNaN(dt.getTime())) continue
        if (ev.event_time) {
          const [h, m] = ev.event_time.split(":").map(Number)
          if (!isNaN(h) && !isNaN(m)) dt.setHours(h, m, 0)
        }
        if (dt > now) {
          upcoming.push({ title: ev.title, time: ev.event_time ?? "all day" })
        }
      }
      for (const s of day.schedule ?? []) {
        const sTime = (s as any).time || s.start_time
        const sTitle = (s as any).title || (s as any).subject || s.subject_name || ""
        if (sTime) {
          const [h, m] = sTime.split(":").map(Number)
          if (!isNaN(h) && !isNaN(m)) {
            const dt = new Date(now)
            dt.setHours(h, m, 0)
            if (dt > now && day.date === now.toISOString().slice(0, 10)) {
              upcoming.push({ title: sTitle, time: sTime })
            }
          }
        }
      }
    }
  }

  upcoming.sort((a, b) => a.time.localeCompare(b.time))

  if (upcoming.length === 0) return <div className="opacity-40">—</div>

  return (
    <>
      {upcoming.map((e, i) => (
        <div key={i} className="opacity-70">
          <span className="opacity-50 tabular-nums">{e.time}</span>{"  "}{e.title}
        </div>
      ))}
    </>
  )
}

export default function TerminalData() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const pausedRef = useRef(false)
  const queryClient = useQueryClient()
  const [liveFlash, setLiveFlash] = useState(false)

  // Real-time invalidation via WebSocket — replaces polling for most queries
  const handleLiveEvent = useCallback(
    (event: ReturnType<typeof useLoraLive extends (h: infer H) => void ? never : never> | any) => {
      if (event.type !== "intent_executed") return

      // Flash the LIVE indicator
      setLiveFlash(true)
      setTimeout(() => setLiveFlash(false), 800)

      const { module } = event.payload ?? {}

      // Invalidate query keys based on the module that changed
      const moduleQueryMap: Record<string, string[][]> = {
        tasks:    [["terminal-tasks"]],
        events:   [["terminal-events"]],
        calendar: [["terminal-events"]],
        health:   [["terminal-health"]],
        finance:  [["terminal-finance"]],
        workout:  [["terminal-workout"]],
        goals:    [["terminal-goals"]],
        skills:   [["terminal-skills"]],
      }
      const keys = moduleQueryMap[module] ?? []
      keys.forEach(queryKey => queryClient.invalidateQueries({ queryKey }))

      // Always refresh tasks (cross-cutting concern for scheduling)
      if (module !== "tasks") {
        queryClient.invalidateQueries({ queryKey: ["terminal-tasks"] })
      }
    },
    [queryClient]
  )

  useLoraLive(handleLiveEvent)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    let id: ReturnType<typeof setTimeout>
    let pos = 0
    let dir = 1

    const tick = () => {
      if (pausedRef.current || el.scrollHeight <= el.clientHeight) {
        id = setTimeout(tick, 200)
        return
      }
      pos += dir * 0.8
      if (dir === 1 && pos >= el.scrollHeight - el.clientHeight) {
        pos = el.scrollHeight - el.clientHeight
        dir = -1
        id = setTimeout(tick, 6000)
        el.scrollTop = pos
        return
      }
      if (dir === -1 && pos <= 0) {
        pos = 0
        dir = 1
        id = setTimeout(tick, 6000)
        el.scrollTop = 0
        return
      }
      el.scrollTop = pos
      id = setTimeout(tick, 100)
    }

    id = setTimeout(tick, 3000)

    const onEnter = () => { pausedRef.current = true }
    const onLeave = () => { pausedRef.current = false }
    el.addEventListener("mouseenter", onEnter)
    el.addEventListener("mouseleave", onLeave)

    return () => {
      clearTimeout(id)
      el.removeEventListener("mouseenter", onEnter)
      el.removeEventListener("mouseleave", onLeave)
    }
  }, [])

  return (
    <div ref={scrollRef} className="px-6 py-6 text-sm leading-snug select-none font-mono w-full h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="opacity-30 text-base">$ lora dashboard</div>
        {/* Live indicator — pulses green when a WebSocket event arrives */}
        <div className={`flex items-center gap-1 text-xs transition-all duration-300 ${liveFlash ? "opacity-100" : "opacity-20"}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${liveFlash ? "bg-green-400 shadow-[0_0_6px_#4ade80]" : "bg-white/40"}`} />
          <span className={liveFlash ? "text-green-400" : ""}>LIVE</span>
        </div>
      </div>
      <div className="opacity-10 mb-4 text-xs">{"─".repeat(30)}</div>

      <div className="mb-3">
        <div className="opacity-30 text-xs mb-1">$ date</div>
        <div className="ml-3">
          <DateSection />
        </div>
      </div>

      <div className="mb-3">
        <div className="opacity-30 text-xs mb-1">$ weather</div>
        <div className="ml-3">
          <WeatherSection />
        </div>
      </div>

      <div className="mb-3">
        <div className="opacity-30 text-xs mb-1">$ tasks</div>
        <div className="ml-3">
          <TasksSection />
        </div>
      </div>

      <div className="mb-3">
        <div className="opacity-30 text-xs mb-1">$ server</div>
        <div className="ml-3">
          <ServerSection />
        </div>
      </div>

      <div className="mb-0">
        <div className="opacity-30 text-xs mb-1">$ events</div>
        <div className="ml-3">
          <EventsSection />
        </div>
      </div>
    </div>
  )
}
