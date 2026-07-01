import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { twMerge } from "tailwind-merge"
import { fetchProfile } from "../api/auth"
import { fetchWeek } from "../api/queries/calendar"
import { fetchFinanceHistory, fetchFinanceSummary } from "../api/queries/finance"
import { fetchTasks } from "../api/queries/tasks"
import { fetchProjects } from "../api/queries/projects"
import { fetchShopping } from "../api/queries/shopping"
import { fetchHealthSummary } from "../api/queries/health"
import { fetchDailyNutrition } from "../api/queries/nutrition"
import { CalendarWidget } from "../components/charts/CalendarWidget"
import { FinanceWidget } from "../components/charts/FinanceWidget"
import { TasksWidget } from "../components/charts/TasksWidget"
import { ProjectsWidget } from "../components/charts/ProjectsWidget"
import { WeatherWidget } from "../components/charts/WeatherWidget"
import { MoodWidget } from "../components/charts/MoodWidget"
import { HealthWidget } from "../components/charts/HealthWidget"
import { ShoppingWidget } from "../components/charts/ShoppingWidget"
import { NutritionWidget } from "../components/charts/NutritionWidget"
import { ViewContainer } from "../components/ViewContainer"
import { Spinner } from "../components/ui/Spinner"
import { QuickActions } from "../components/QuickActions"
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from "recharts"
import { PieChart, Pie, Cell, ResponsiveContainer as PieResponsive } from "recharts"
import { CheckCircle2, Circle, ListChecks, Wallet, CalendarDays as CalendarIcon, Sparkles, ShoppingCart, Heart, Apple, Smile } from "lucide-react"

type ExpandedWidget = "calendar" | "finance" | "tasks" | "projects" | "weather" | "health" | "mood" | "shopping" | "nutrition" | null

const statusColor: Record<string, string> = {
  active: "bg-emerald-500",
  paused: "bg-yellow-500",
  completed: "bg-primary",
}

const systemRed = "#FF3B30"
const systemEmerald = "#34C759"

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("ro-RO", { style: "currency", currency: "RON", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n)
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 18) return "Good afternoon"
  return "Good evening"
}

function SubCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={twMerge("glass-strong rounded-2xl p-5 shadow-apple-heavy", className)}>
      {children}
    </div>
  )
}

function ExpandedCalendar() {
  const { data: week, isLoading } = useQuery({
    queryKey: ["calendar", "dashboard"],
    queryFn: () => fetchWeek(new Date()),
    refetchInterval: 60_000,
  })
  if (isLoading) return <Spinner className="py-16" />
  if (!week) return <p className="text-apple-caption1 text-text-muted">No data</p>
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {week.map((day) => {
        const hasAny = day.events.length > 0 || day.schedule.length > 0
        return (
          <SubCard key={day.date}>
            <h4 className="text-apple-footnote font-semibold text-text-primary mb-2">{day.day_name} <span className="text-text-secondary font-normal">{day.date}</span></h4>
            {!hasAny ? (
              <p className="text-apple-caption1 text-text-muted">Nothing scheduled</p>
            ) : (
              <div className="space-y-2 max-h-[320px] overflow-y-auto">
                {day.events.map((ev) => (
                  <div key={ev.id} className="flex items-start gap-2 text-sm">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                    <div>
                      <p className="text-text-primary">{ev.title}</p>
                      {ev.event_time && <p className="text-apple-caption2 text-text-muted">{ev.event_time}</p>}
                    </div>
                  </div>
                ))}
                {day.schedule.map((s) => (
                  <div key={s.id} className="flex items-start gap-2 text-sm">
                    <div className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 shrink-0" />
                    <div>
                      <p className="text-text-primary">{s.subject_name}</p>
                      <p className="text-apple-caption2 text-text-muted">{s.start_time?.slice(0, 5)}-{s.end_time?.slice(0, 5)}{s.room ? ` · ${s.room}` : ""}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SubCard>
        )
      })}
    </div>
  )
}

function ExpandedFinance() {
  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ["finance-history", 30],
    queryFn: () => fetchFinanceHistory(30),
    refetchInterval: 60_000,
  })
  const { data: summary, isLoading: sumLoading } = useQuery({
    queryKey: ["finance-summary"],
    queryFn: fetchFinanceSummary,
    refetchInterval: 60_000,
  })
  if (histLoading || sumLoading) return <Spinner className="py-16" />

  const dailyMap = new Map<string, { income: number; expense: number }>()
  for (const tx of history ?? []) {
    if (!dailyMap.has(tx.transaction_date)) dailyMap.set(tx.transaction_date, { income: 0, expense: 0 })
    const d = dailyMap.get(tx.transaction_date)!
    if (tx.type === "income") d.income += tx.amount
    else d.expense += tx.amount
  }
  const chartData = Array.from(dailyMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-14)
    .map(([date, vals]) => ({
      date: new Date(date + "T00:00:00").toLocaleDateString("ro-RO", { day: "numeric", month: "short" }),
      income: vals.income,
      expense: vals.expense,
    }))

  const bal = summary?.summary?.balance ?? 0
  const inc = summary?.summary?.income ?? 0
  const exp = summary?.summary?.expense ?? 0

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Balance</p><p className="text-2xl font-bold text-text-primary">{fmtCurrency(bal)}</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Income</p><p className="text-2xl font-bold text-emerald-500">{fmtCurrency(inc)}</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Expenses</p><p className="text-2xl font-bold text-red-500">{fmtCurrency(exp)}</p></SubCard>
      </div>
      {chartData.length > 0 && (
        <SubCard className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="efi" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={systemEmerald} stopOpacity={0.2} /><stop offset="100%" stopColor={systemEmerald} stopOpacity={0} /></linearGradient>
                <linearGradient id="efe" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={systemRed} stopOpacity={0.2} /><stop offset="100%" stopColor={systemRed} stopOpacity={0} /></linearGradient>
              </defs>
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} />
              <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 8, fontSize: 12 }} labelStyle={{ color: "var(--color-text-secondary)", marginBottom: 4 }} />
              <Area type="monotone" dataKey="income" stroke={systemEmerald} strokeWidth={2} fill="url(#efi)" dot={false} />
              <Area type="monotone" dataKey="expense" stroke={systemRed} strokeWidth={2} fill="url(#efe)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </SubCard>
      )}
      {history && history.length > 0 && (
        <SubCard className="overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50"><h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Recent Transactions</h4></div>
          {history.slice(0, 10).map((tx, idx) => (
            <div key={tx.id} className={`flex items-center justify-between px-4 py-2.5 ${idx < Math.min(history.length, 10) - 1 ? "border-b border-border/30 ml-4" : ""}`}>
              <div className="flex items-center gap-2.5 min-w-0">
                <div className={twMerge("w-1.5 h-1.5 rounded-full shrink-0", tx.type === "income" ? "bg-emerald-500" : "bg-red-500")} />
                <span className="text-apple-caption1 text-text-primary truncate">{tx.description || tx.category}</span>
              </div>
              <span className={twMerge("text-apple-caption1 shrink-0 ml-2 tabular-nums", tx.type === "income" ? "text-emerald-500" : "text-red-500")}>{tx.type === "income" ? "+" : "-"}{fmtCurrency(tx.amount)}</span>
            </div>
          ))}
        </SubCard>
      )}
    </div>
  )
}

function ExpandedTasks() {
  const { data: tasks, isLoading } = useQuery({ queryKey: ["tasks"], queryFn: () => fetchTasks("all"), refetchInterval: 60_000 })
  if (isLoading) return <Spinner className="py-16" />
  if (!tasks || tasks.length === 0) return <p className="text-apple-caption1 text-text-muted">No tasks yet</p>
  const done = tasks.filter((t) => t.status === "done")
  const pending = tasks.filter((t) => t.status !== "done")
  const pieData = [{ name: "Done", value: done.length }, { name: "Pending", value: Math.max(pending.length, 0) }]
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-6">
        <div className="w-32 h-32 shrink-0">
          <PieResponsive width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={32} outerRadius={52} startAngle={90} endAngle={-270} dataKey="value" stroke="none">
                <Cell fill="url(#etd)" /><Cell fill="var(--color-border)" />
              </Pie>
            </PieChart>
          </PieResponsive>
          <svg width="0" height="0"><defs><linearGradient id="etd" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#7c3aed" /><stop offset="100%" stopColor="#a78bfa" /></linearGradient></defs></svg>
        </div>
        <div><p className="text-3xl font-bold text-text-primary">{done.length}<span className="text-lg text-text-secondary ml-1">/ {tasks.length}</span></p><p className="text-xs text-text-muted mt-1">{pending.length} pending</p></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SubCard className="overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50"><h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Pending</h4></div>
          {pending.length === 0 ? <p className="text-apple-caption1 text-text-muted px-4 py-3">All clear!</p> : pending.map((t, idx) => (
            <div key={t.id} className={`flex items-center gap-2.5 px-4 py-2.5 ${idx < pending.length - 1 ? "border-b border-border/30 ml-4" : ""}`}>
              <Circle className="w-3.5 h-3.5 text-text-muted shrink-0" />
              <span className="text-apple-caption1 text-text-primary truncate">{t.title}</span>
              {t.priority === "high" && <span className="text-apple-caption2 text-red-500 shrink-0">high</span>}
            </div>
          ))}
        </SubCard>
        <SubCard className="overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50"><h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Done</h4></div>
          {done.length === 0 ? <p className="text-apple-caption1 text-text-muted px-4 py-3">Nothing done yet</p> : done.map((t, idx) => (
            <div key={t.id} className={`flex items-center gap-2.5 px-4 py-2.5 ${idx < done.length - 1 ? "border-b border-border/30 ml-4" : ""}`}>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
              <span className="text-apple-caption1 text-text-secondary line-through truncate">{t.title}</span>
            </div>
          ))}
        </SubCard>
      </div>
    </div>
  )
}

function ExpandedProjects() {
  const { data: projects, isLoading } = useQuery({ queryKey: ["projects"], queryFn: fetchProjects, refetchInterval: 60_000 })
  if (isLoading) return <Spinner className="py-16" />
  if (!projects || projects.length === 0) return <p className="text-apple-caption1 text-text-muted">No projects yet</p>
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {projects.map((p) => (
        <SubCard key={p.id}>
          <div className="flex items-center gap-2 mb-2">
            <div className={twMerge("w-2 h-2 rounded-full shrink-0", statusColor[p.status] ?? "bg-text-muted")} />
            <h4 className="text-apple-footnote font-semibold text-text-primary truncate">{p.name}</h4>
            <span className="text-apple-caption2 text-text-muted shrink-0">{p.status}</span>
          </div>
          <div className="h-1 bg-border rounded-full overflow-hidden mb-2"><div className="h-full bg-violet-500 rounded-full transition-all" style={{ width: `${p.progress_pct ?? 0}%` }} /></div>
          <div className="flex items-center gap-3 text-apple-caption2 text-text-muted">
            {p.completed_tasks !== undefined && <span>{p.completed_tasks}/{p.task_count} tasks</span>}
            <span>{p.progress_pct}%</span>
            {p.deadline && <span>Due {p.deadline}</span>}
          </div>
          {p.tasks && p.tasks.length > 0 && (
            <div className="mt-2 pt-2 border-t border-border space-y-0.5">
              {p.tasks.slice(0, 5).map((t) => (
                <div key={t.id} className="flex items-center gap-1.5 text-apple-caption2">
                  <div className={twMerge("w-1 h-1 rounded-full shrink-0", t.status === "done" ? "bg-emerald-500" : "bg-text-muted")} />
                  <span className={twMerge("truncate", t.status === "done" ? "text-text-secondary line-through" : "text-text-primary")}>{t.title}</span>
                </div>
              ))}
            </div>
          )}
        </SubCard>
      ))}
    </div>
  )
}

function ExpandedWeather() {
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null)
  useEffect(() => { navigator.geolocation.getCurrentPosition((pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }), () => {}) }, [])
  const { data, isLoading } = useQuery({
    queryKey: ["weather", "expanded", coords?.lat, coords?.lon],
    queryFn: () => fetch(`/api/weather?lat=${coords!.lat}&lon=${coords!.lon}`).then((r) => r.json()),
    enabled: !!coords,
    refetchInterval: 300_000,
  })
  if (isLoading) return <Spinner className="py-16" />
  const w = data?.current
  const forecast = data?.forecast ?? []
  if (!w) return <p className="text-apple-caption1 text-text-muted">No weather data</p>

  const emoji = (icon: string) => ({ "01d": "☀️","01n": "🌙","02d": "⛅","02n": "☁️","03d": "☁️","03n": "☁️","04d": "☁️","04n": "☁️","09d": "🌧","09n": "🌧","10d": "🌦","10n": "🌧","11d": "⛈","11n": "⛈","13d": "🌨","13n": "🌨","50d": "🌫","50n": "🌫"})[icon] ?? "🌤"
  const dayLabel = (dateStr: string) => {
    const d = new Date(dateStr + "T12:00:00"); const today = new Date(); today.setHours(12, 0, 0, 0)
    const diff = Math.round((d.getTime() - today.getTime()) / 86400000)
    if (diff === 0) return "Today"; if (diff === 1) return "Tomorrow"
    return d.toLocaleDateString("en-US", { weekday: "short" })
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Temperature</p><p className="text-3xl font-bold text-text-primary">{Math.round(w.temp)}°</p><p className="text-apple-caption1 text-text-muted capitalize">{w.condition}</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Feels Like</p><p className="text-2xl font-bold text-text-primary">{Math.round(w.feels_like)}°</p><p className="text-apple-caption1 text-text-muted">H: {Math.round(w.temp_max)}° L: {Math.round(w.temp_min)}°</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Details</p><p className="text-2xl font-bold text-text-primary">{w.humidity}%</p><p className="text-apple-caption1 text-text-muted">{w.wind_speed?.toFixed(1)} m/s · {w.city}</p></SubCard>
      </div>
      {forecast.length > 0 && (
        <SubCard><h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider mb-4">5-Day Forecast</h4>
          <div className="grid grid-cols-5 gap-3">{forecast.slice(0, 5).map((day: any) => (
            <div key={day.date} className="text-center py-3 rounded-xl bg-white/40 dark:bg-white/[0.04]">
              <p className="text-xs text-text-muted font-medium mb-1">{dayLabel(day.date)}</p>
              <p className="text-2xl mb-1">{emoji(day.icon)}</p>
              <p className="text-sm font-semibold text-text-primary">{Math.round(day.temp_max)}°</p>
              <p className="text-xs text-text-muted">{Math.round(day.temp_min)}°</p>
            </div>
          ))}</div>
        </SubCard>
      )}
    </div>
  )
}

function ExpandedHealth() {
  const { data, isLoading } = useQuery({ queryKey: ["health-summary"], queryFn: fetchHealthSummary, refetchInterval: 60_000 })
  if (isLoading) return <Spinner className="py-16" />
  if (!data?.history?.length) return <p className="text-apple-caption1 text-text-muted">No health data</p>
  const last7 = data.history.slice(-7)
  const avgSleep = last7.reduce((s, h) => s + (h.sleep_hours ?? 0), 0) / last7.filter(h => h.sleep_hours).length || 0
  const avgWater = Math.round(last7.reduce((s, h) => s + (h.water_ml ?? 0), 0) / last7.filter(h => h.water_ml).length) || 0
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Avg Sleep</p><p className="text-2xl font-bold text-text-primary">{avgSleep.toFixed(1)}h</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Avg Water</p><p className="text-2xl font-bold text-sky-500">{avgWater}ml</p></SubCard>
      </div>
      <SubCard className="overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50"><h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Last 14 Days</h4></div>
        {data.history.slice(-14).reverse().map((h, idx, arr) => (
          <div key={h.log_date} className={`flex items-center justify-between px-4 py-2 ${idx < arr.length - 1 ? "border-b border-border/30 ml-4" : ""}`}>
            <span className="text-apple-caption2 text-text-muted w-24">{h.log_date}</span>
            <span className="text-apple-caption2 text-text-primary tabular-nums w-16">{h.sleep_hours ? `${h.sleep_hours}h` : "-"}</span>
            <span className="text-apple-caption2 text-text-primary tabular-nums w-16">{h.water_ml ? `${h.water_ml}ml` : "-"}</span>
            <span className="text-apple-caption2 text-text-primary tabular-nums w-12">{h.cigarettes ?? "-"}</span>
          </div>
        ))}
      </SubCard>
    </div>
  )
}

function ExpandedShopping() {
  const { data: items, isLoading } = useQuery({ queryKey: ["shopping"], queryFn: fetchShopping, refetchInterval: 60_000 })
  if (isLoading) return <Spinner className="py-16" />
  if (!items?.length) return <p className="text-apple-caption1 text-text-muted">Shopping list empty</p>
  const pending = items.filter((i) => !i.is_bought)
  const bought = items.filter((i) => i.is_bought)
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <SubCard className="overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50"><h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">To Buy ({pending.length})</h4></div>
        {pending.length === 0 ? <p className="text-apple-caption1 text-text-muted px-4 py-3">All bought!</p> : pending.map((i, idx) => (
          <div key={i.id} className={`flex items-center gap-2.5 px-4 py-2.5 ${idx < pending.length - 1 ? "border-b border-border/30 ml-4" : ""}`}>
            <Circle className="w-3.5 h-3.5 text-text-muted shrink-0" />
            <span className="text-apple-caption1 text-text-primary truncate">{i.item}</span>
            {i.category && <span className="text-apple-caption2 text-text-muted shrink-0">{i.category}</span>}
          </div>
        ))}
      </SubCard>
      <SubCard className="overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50"><h4 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">Bought ({bought.length})</h4></div>
        {bought.length === 0 ? <p className="text-apple-caption1 text-text-muted px-4 py-3">Nothing bought yet</p> : bought.map((i, idx) => (
          <div key={i.id} className={`flex items-center gap-2.5 px-4 py-2.5 ${idx < bought.length - 1 ? "border-b border-border/30 ml-4" : ""}`}>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
            <span className="text-apple-caption1 text-text-secondary line-through truncate">{i.item}</span>
          </div>
        ))}
      </SubCard>
    </div>
  )
}

function ExpandedNutrition() {
  const { data, isLoading } = useQuery({ queryKey: ["nutrition"], queryFn: fetchDailyNutrition, refetchInterval: 60_000 })
  if (isLoading) return <Spinner className="py-16" />
  if (!data?.meals?.length) return <p className="text-apple-caption1 text-text-muted">No meals logged today</p>
  const grouped = data.meals.reduce<Record<string, typeof data.meals>>((acc, m) => { (acc[m.meal_type] ??= []).push(m); return acc }, {})
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Calories</p><p className="text-2xl font-bold text-text-primary">{data.totals.calories}</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Protein</p><p className="text-2xl font-bold text-text-primary">{data.totals.protein}g</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Carbs</p><p className="text-2xl font-bold text-text-primary">{data.totals.carbs}g</p></SubCard>
        <SubCard><p className="text-apple-caption2 text-text-muted mb-0.5">Fat</p><p className="text-2xl font-bold text-text-primary">{data.totals.fat}g</p></SubCard>
      </div>
      {Object.entries(grouped).map(([type, meals]) => (
        <SubCard key={type} className="overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50"><h4 className="text-apple-footnote font-semibold capitalize text-text-secondary tracking-wider">{type}</h4></div>
          {meals.map((m, idx) => (
            <div key={m.id} className={`flex items-center justify-between px-4 py-2 ${idx < meals.length - 1 ? "border-b border-border/30 ml-4" : ""}`}>
              <span className="text-apple-caption1 text-text-primary truncate">{m.description}</span>
              <span className="text-apple-caption2 text-text-muted tabular-nums shrink-0 ml-2">{m.calories}cal</span>
            </div>
          ))}
        </SubCard>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [expanded, setExpanded] = useState<ExpandedWidget>(null)
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: fetchProfile, refetchInterval: 60_000 })
  const { data: tasks } = useQuery({ queryKey: ["tasks"], queryFn: () => fetchTasks("all"), refetchInterval: 60_000 })
  const { data: summary } = useQuery({ queryKey: ["finance-summary"], queryFn: fetchFinanceSummary, refetchInterval: 60_000 })
  const { data: week } = useQuery({ queryKey: ["calendar", "dashboard"], queryFn: () => fetchWeek(new Date()), refetchInterval: 60_000 })

  const now = new Date()
  const dateStr = now.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", year: "numeric" })
  const greeting = getGreeting()

  const tasksDue = tasks?.filter((t) => t.status !== "done").length ?? 0
  const balance = summary?.summary?.balance ?? 0
  const todayStr = now.toISOString().slice(0, 10)
  const todayEvents = week?.find((d) => d.date === todayStr)
  const eventsCount = (todayEvents?.events.length ?? 0) + (todayEvents?.schedule.length ?? 0)

  const stats = [
    { icon: ListChecks, label: "Tasks due", value: `${tasksDue}`, color: "text-primary" },
    { icon: Wallet, label: "Balance", value: fmtCurrency(balance), color: "text-text-primary" },
    { icon: CalendarIcon, label: "Today", value: `${eventsCount} events`, color: "text-accent" },
  ]

  const nameInitial = profile?.name?.charAt(0).toUpperCase() ?? "L"

  const widgets = [
    { key: "calendar" as const, Widget: CalendarWidget },
    { key: "tasks" as const, Widget: TasksWidget },
    { key: "finance" as const, Widget: FinanceWidget },
    { key: "health" as const, Widget: HealthWidget },
    { key: "projects" as const, Widget: ProjectsWidget },
    { key: "shopping" as const, Widget: ShoppingWidget },
    { key: "nutrition" as const, Widget: NutritionWidget },
    { key: "mood" as const, Widget: MoodWidget },
    { key: "weather" as const, Widget: WeatherWidget },
  ]

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div className="space-y-6">
          {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold text-text-primary tracking-tight">{greeting}</h1>
              <Sparkles className="w-5 h-5 text-primary/60" />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-apple-footnote text-text-secondary">{dateStr}</span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full glass-strong text-apple-caption2 text-text-secondary font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />{tasksDue} due
              </span>
            </div>
          </div>
          <div className="avatar-circle">{nameInitial}</div>
        </div>
      </motion.div>

      {/* Quick Actions */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.05 }}>
        <QuickActions />
      </motion.div>

      {/* Stats row */}
      <motion.div className="grid grid-cols-3 gap-3" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
        {stats.map(({ icon: Icon, label, value, color }, i) => (
          <motion.div key={label} whileTap={{ scale: 0.97 }} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.04 }}
              className="card-liquid shadow-apple-heavy">
              <div className="card-liquid-content p-4 flex flex-col items-center justify-center text-center hover-lift">
                <Icon className={`w-5 h-5 ${color} mb-1.5`} />
                <span className="text-xl font-bold text-text-primary tabular-nums">{value}</span>
                <span className="text-apple-caption2 text-text-muted mt-0.5">{label}</span>
              </div>
            </motion.div>
        ))}
      </motion.div>

      {/* Widget grid */}
      <motion.div className="grid grid-cols-1 md:grid-cols-2 gap-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ staggerChildren: 0.06, delayChildren: 0.15 }}>
        {/* Calendar — full width */}
        <motion.div key="calendar" className="md:col-span-2" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: "easeOut" }}>
          <CalendarWidget onExpand={() => setExpanded("calendar")} />
        </motion.div>

        {/* Rest */}
        {widgets.slice(1).map(({ key, Widget }) => (
          <motion.div key={key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: "easeOut" }}>
            <Widget onExpand={() => setExpanded(key)} />
          </motion.div>
        ))}
      </motion.div>

      <AnimatePresence>
        {expanded && (
          <ViewContainer title={expanded.charAt(0).toUpperCase() + expanded.slice(1)} onBack={() => setExpanded(null)}>
            {expanded === "calendar" && <ExpandedCalendar />}
            {expanded === "finance" && <ExpandedFinance />}
            {expanded === "tasks" && <ExpandedTasks />}
            {expanded === "projects" && <ExpandedProjects />}
            {expanded === "weather" && <ExpandedWeather />}
            {expanded === "health" && <ExpandedHealth />}
            {expanded === "shopping" && <ExpandedShopping />}
            {expanded === "nutrition" && <ExpandedNutrition />}
            {expanded === "mood" && <p className="text-apple-caption1 text-text-muted py-8 text-center">Mood detail view coming soon</p>}
          </ViewContainer>
        )}
      </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
