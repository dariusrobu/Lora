import { useQuery } from "@tanstack/react-query"
import { useState, useEffect } from "react"
import { api } from "../../api/client"
import type { Task, CalendarDay } from "../../types"

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
    queryFn: () => fetch("/api/weather?lat=44.43&lon=26.10").then(r => r.json()),
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

const TASKS_MOCK: Task[] = [
  { id: 101, title: "Review AI course final project", priority: "high", status: "pending", created_at: "2026-07-01" },
  { id: 102, title: "Buy groceries for weekend party", priority: "medium", status: "pending", created_at: "2026-07-01" },
  { id: 103, title: "Prepare presentation slides for Monday", priority: "high", status: "pending", created_at: "2026-07-01" },
  { id: 104, title: "Fix staircase light sensor", priority: "low", status: "pending", created_at: "2026-07-01" },
  { id: 105, title: "Call dentist for appointment", priority: "medium", status: "pending", created_at: "2026-07-01" },
  { id: 106, title: "Order replacement filter for vacuum", priority: "low", status: "pending", created_at: "2026-07-01" },
  { id: 107, title: "Write weekly review report", priority: "medium", status: "pending", created_at: "2026-07-01" },
]

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
  const useMock = !tasks || pending.length === 0
  const display = useMock ? TASKS_MOCK : pending
  const top = display.slice(0, 5)

  return (
    <>
      <div><span className="opacity-80">{display.length} pending</span></div>
      {top.map((t) => (
        <div key={t.id} className="flex items-center gap-1.5 opacity-70">
          <span className="opacity-30">○</span>
          <span className="truncate">{t.title}</span>
          {t.priority === "high" && <span className="text-xs opacity-50 shrink-0">●</span>}
        </div>
      ))}
      {display.length > 5 && <div className="opacity-40">+{display.length - 5} more</div>}
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

const EVENTS_MOCK = [
  { time: "09:00", title: "Curs Inteligență Artificială" },
  { time: "10:30", title: "Daily standup meeting" },
  { time: "11:00", title: "Review PRs on GitHub" },
  { time: "13:00", title: "Lunch with Maria" },
  { time: "14:30", title: "Dentist appointment" },
  { time: "17:00", title: "Gym - chest day" },
  { time: "21:00", title: "Netflix & chill" },
]

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
        if (s.time) {
          const [h, m] = s.time.split(":").map(Number)
          if (!isNaN(h) && !isNaN(m)) {
            const dt = new Date(now)
            dt.setHours(h, m, 0)
            if (dt > now && day.date === now.toISOString().slice(0, 10)) {
              upcoming.push({ title: s.title || s.subject || "", time: s.time })
            }
          }
        }
      }
    }
  }

  const list = upcoming.length > 0 ? upcoming : EVENTS_MOCK
  list.sort((a, b) => a.time.localeCompare(b.time))
  const top = list

  if (top.length === 0) return <div className="opacity-40">—</div>

  return (
    <>
      {top.map((e, i) => (
        <div key={i} className="opacity-70">
          <span className="opacity-50 tabular-nums">{e.time}</span>{"  "}{e.title}
        </div>
      ))}
    </>
  )
}

export default function TerminalData() {
  return (
    <div className="px-8 py-8 text-sm leading-snug select-none font-mono w-full">
      <div className="opacity-30 mb-3 text-base">$ lora dashboard</div>
      <div className="opacity-10 mb-4 text-xs">{"─".repeat(36)}</div>

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
