import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchTasks, createTask, completeTask } from "../../api/queries/tasks"
import { WidgetCard } from "./WidgetCard"
import { ListChecks, Plus, Circle, CheckCircle2, Sparkles, Check, Flame, Clock } from "lucide-react"

interface Props { onExpand?: () => void }

const PLACEHOLDERS = ["Buy milk", "Review PR", "Pay bills", "Write tests", "Call dentist", "Plan trip", "Read chapter", "Clean desk", "Fix bug", "Update deps"]

function randomPlaceholder() {
  return PLACEHOLDERS[Math.floor(Math.random() * PLACEHOLDERS.length)]
}

function getDueDot(due_date?: string): { color: string; label: string } | null {
  if (!due_date) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(due_date + "T00:00:00")
  const diff = Math.round((due.getTime() - today.getTime()) / 86400000)
  if (diff < 0) return { color: "bg-red-500", label: `Overdue by ${Math.abs(diff)}d` }
  if (diff === 0) return { color: "bg-orange-500", label: "Due today" }
  if (diff <= 3) return { color: "bg-yellow-500", label: `Due in ${diff}d` }
  return { color: "bg-text-muted", label: due_date }
}

export function TasksWidget({ onExpand }: Props) {
  const [quickTitle, setQuickTitle] = useState("")
  const [quickPriority, setQuickPriority] = useState<"high" | "medium" | "low">("medium")
  const [completing, setCompleting] = useState<Set<number>>(new Set())
  const [placeholder] = useState(randomPlaceholder)
  const qc = useQueryClient()

  const { data: tasks, isLoading, isError, refetch } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => fetchTasks("all"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const createMut = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      setQuickTitle("")
    },
  })
  const completeMut = useMutation({
    mutationFn: completeTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      setTimeout(() => setCompleting(new Set()), 400)
    },
  })

  const done = tasks?.filter((t) => t.status === "done") ?? []
  const pending = tasks?.filter((t) => t.status !== "done") ?? []
  const total = tasks?.length ?? 0
  const pct = total > 0 ? Math.round((done.length / total) * 100) : 0
  const hasData = total > 0

  const handleQuickAdd = () => {
    if (!quickTitle.trim() || createMut.isPending) return
    createMut.mutate({ title: quickTitle.trim(), priority: quickPriority })
  }

  const handleComplete = (id: number) => {
    setCompleting((prev) => new Set(prev).add(id))
    completeMut.mutate(id)
  }

  return (
    <WidgetCard
      icon={<ListChecks className="w-4 h-4" />}
      label="Tasks"
      linkTo="/tasks"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="No tasks yet"
      emptyCTA={
        <div className="flex gap-1.5 w-full max-w-64">
          <input value={quickTitle} onChange={(e) => setQuickTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
            placeholder={placeholder} autoFocus
            className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 focus:ring-2 focus:ring-primary/20 transition-all" />
          <button onClick={handleQuickAdd} disabled={!quickTitle.trim() || createMut.isPending}
            className="w-8 h-8 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0">
            <Plus className="w-4 h-4" />
          </button>
        </div>
      }
    >
      {/* Option A: Hero Progress Ring (Apple Fitness style) + Prominent Metrics */}
      <div className="flex flex-col sm:flex-row items-center gap-6 mb-6 p-4 rounded-2xl bg-white/[0.015] border border-white/[0.04]">
        {/* Animated Big Progress Ring */}
        <div className="relative w-28 h-28 sm:w-32 sm:h-32 shrink-0 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="none"
              stroke="rgba(255, 255, 255, 0.05)"
              strokeWidth="8"
            />
            {pct > 0 && (
              <motion.circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="url(#taskRingGradient)"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={251.327}
                initial={{ strokeDashoffset: 251.327 }}
                animate={{ strokeDashoffset: 251.327 - (251.327 * pct) / 100 }}
                transition={{ duration: 1, ease: [0.34, 1.56, 0.64, 1] }}
              />
            )}
            <defs>
              <linearGradient id="taskRingGradient" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={pct === 100 ? "#10B981" : "#6366F1"} />
                <stop offset="100%" stopColor={pct === 100 ? "#34D399" : "#A855F7"} />
              </linearGradient>
            </defs>
          </svg>

          {/* Center Content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <motion.span
              key={pct}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="text-2xl sm:text-3xl font-black text-white tracking-tight tabular-nums"
            >
              {pct}%
            </motion.span>
            <span className="text-[10px] font-bold text-indigo-300/80 uppercase tracking-widest mt-0.5">
              {pct === 100 ? "Complet" : "Gata"}
            </span>
          </div>
        </div>

        {/* 3 Prominent Secondary Metrics */}
        <div className="grid grid-cols-3 gap-4 w-full sm:divide-x sm:divide-white/[0.06]">
          {/* Active Tasks */}
          <div className="flex flex-col items-center sm:items-start sm:pl-2">
            <div className="flex items-center gap-1.5 mb-1 text-text-muted">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider">Rămase</span>
            </div>
            <motion.span
              key={pending.length}
              initial={{ y: -4, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="text-2xl sm:text-3xl font-black text-white tabular-nums tracking-tight"
            >
              {pending.length}
            </motion.span>
          </div>

          {/* Done Tasks */}
          <div className="flex flex-col items-center sm:items-start sm:px-4">
            <div className="flex items-center gap-1.5 mb-1 text-text-muted">
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider">Gata</span>
            </div>
            <motion.span
              key={done.length}
              initial={{ y: -4, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="text-2xl sm:text-3xl font-black text-emerald-400 tabular-nums tracking-tight"
            >
              {done.length}
            </motion.span>
          </div>

          {/* Urgent / High Priority */}
          <div className="flex flex-col items-center sm:items-start sm:px-4">
            <div className="flex items-center gap-1.5 mb-1 text-text-muted">
              <Flame className="w-3.5 h-3.5 text-rose-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider">Urgente</span>
            </div>
            <motion.span
              key={pending.filter((t) => t.priority === "high").length}
              initial={{ y: -4, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className={`text-2xl sm:text-3xl font-black tabular-nums tracking-tight ${
                pending.filter((t) => t.priority === "high").length > 0 ? "text-rose-400" : "text-text-muted"
              }`}
            >
              {pending.filter((t) => t.priority === "high").length}
            </motion.span>
          </div>
        </div>
      </div>

      {/* Task List Header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
          Task-uri Active ({pending.length})
        </span>
        {pct === 100 && (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400">
            <Sparkles className="w-3.5 h-3.5" /> Toate finalizate!
          </span>
        )}
      </div>

      {/* Fluid Task List */}
      {pending.length > 0 ? (
        <div className="space-y-1.5 mb-5">
          {pending.slice(0, 5).map((t, idx) => {
            const dueDot = getDueDot(t.due_date)
            const isCompleting = completing.has(t.id)
            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.04, duration: 0.2 }}
                className="group flex items-center justify-between p-2.5 rounded-xl hover:bg-white/[0.035] border border-transparent hover:border-white/[0.04] transition-all"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  {/* Magnetic Check Button */}
                  <motion.button
                    whileTap={{ scale: 0.85 }}
                    onClick={() => handleComplete(t.id)}
                    className="w-5 h-5 rounded-full border border-white/20 group-hover:border-indigo-400 group-hover:bg-indigo-500/10 flex items-center justify-center shrink-0 transition-colors"
                  >
                    {isCompleting ? (
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      </motion.div>
                    ) : (
                      <Circle className="w-3 h-3 text-transparent group-hover:text-indigo-400/40 transition-colors" />
                    )}
                  </motion.button>

                  {/* Task Title */}
                  <span
                    className={`text-sm font-medium truncate transition-colors ${
                      isCompleting ? "text-zinc-500 line-through" : "text-zinc-200 group-hover:text-white"
                    }`}
                  >
                    {t.title}
                  </span>
                </div>

                {/* Badges / Meta */}
                <div className="flex items-center gap-2 shrink-0 ml-3">
                  {t.priority === "high" && (
                    <span className="px-2 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/25 text-rose-400 text-[10px] font-bold uppercase tracking-wider">
                      urgent
                    </span>
                  )}
                  {t.priority === "medium" && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/25 text-amber-400 text-[10px] font-medium">
                      med
                    </span>
                  )}
                  {dueDot && (
                    <span className="flex items-center gap-1 text-[11px] text-zinc-400 font-medium">
                      <span className={`w-1.5 h-1.5 rounded-full ${dueDot.color}`} />
                      {dueDot.label}
                    </span>
                  )}
                </div>
              </motion.div>
            )
          })}
          {pending.length > 5 && (
            <p className="text-xs text-zinc-500 pl-3 pt-1">
              +{pending.length - 5} task-uri în plus
            </p>
          )}
        </div>
      ) : (
        <div className="py-6 text-center text-zinc-500 text-xs">
          Niciun task activ în acest moment.
        </div>
      )}

      {/* Quick Add Bar (Linear Style) */}
      <div className="flex items-center gap-2 pt-2 border-t border-white/[0.05]">
        <input
          value={quickTitle}
          onChange={(e) => setQuickTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleQuickAdd()
          }}
          placeholder={placeholder}
          className="flex-1 bg-white/[0.03] hover:bg-white/[0.05] focus:bg-white/[0.06] border border-white/[0.08] focus:border-indigo-400/40 rounded-xl py-2 px-3.5 text-xs text-white placeholder:text-zinc-500 outline-none transition-all"
        />
        <div className="flex items-center gap-1 bg-white/[0.02] border border-white/[0.06] rounded-xl p-1 shrink-0">
          {(["high", "medium", "low"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setQuickPriority(p)}
              className={`px-2 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                quickPriority === p
                  ? p === "high"
                    ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                    : p === "medium"
                    ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    : "bg-white/[0.1] text-white border border-white/20"
                  : "text-zinc-500 hover:text-zinc-300 border border-transparent"
              }`}
            >
              {p === "high" ? "H" : p === "medium" ? "M" : "L"}
            </button>
          ))}
        </div>
        <motion.button
          onClick={handleQuickAdd}
          disabled={!quickTitle.trim() || createMut.isPending}
          whileTap={{ scale: 0.95 }}
          className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary to-accent text-white disabled:opacity-30 transition-all flex items-center justify-center shrink-0 shadow-[0_2px_12px_rgba(99,102,241,0.3)] hover:scale-105"
        >
          <Plus className="w-4 h-4" />
        </motion.button>
      </div>
    </WidgetCard>
  )
}
