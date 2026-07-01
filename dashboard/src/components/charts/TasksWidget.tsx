import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchTasks, createTask, completeTask } from "../../api/queries/tasks"
import { WidgetCard } from "./WidgetCard"
import { ListChecks, Plus, Circle, CheckCircle2, Sparkles } from "lucide-react"

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
      {/* Hero — animated ring + done count */}
      <div className="flex items-center gap-3 mb-3">
        <div className="relative w-14 h-14 shrink-0">
          <svg className="w-14 h-14 -rotate-90" viewBox="0 0 36 36">
            <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--color-border)" strokeWidth="3" />
            {pct > 0 ? (
              <motion.circle cx="18" cy="18" r="15.5" fill="none" stroke="url(#taskArc)" strokeWidth="3"
                strokeLinecap="round"
                initial={{ strokeDasharray: `${0} ${100}` }}
                animate={{ strokeDasharray: `${pct} ${100 - pct}` }}
                transition={{ duration: 0.8, ease: [0.34, 1.56, 0.64, 1] }} />
            ) : (
              <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--color-border)" strokeWidth="2"
                strokeDasharray="2 4" strokeLinecap="round" opacity={0.4} />
            )}
            <defs>
              <linearGradient id="taskArc" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#7c3aed" /><stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
            </defs>
          </svg>
          <motion.span
            key={pct}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="absolute inset-0 flex items-center justify-center text-xs font-bold text-text-primary">
            {pct}%
          </motion.span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5">
            <motion.span key={done.length} initial={{ y: -4, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
              className="text-xl font-bold text-text-primary">{done.length}</motion.span>
            <span className="text-xs text-text-secondary">/ {total} done</span>
          </div>
          <div className="flex gap-2 mt-1.5">
            {pending.filter((t) => t.priority === "high").length > 0 && (
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}
                className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-500 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                {pending.filter((t) => t.priority === "high").length} high
              </motion.span>
            )}
            {pending.filter((t) => t.priority === "medium").length > 0 && (
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}
                className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-500 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
                {pending.filter((t) => t.priority === "medium").length} med
              </motion.span>
            )}
            {(done.length > 0 && done.length <= 3) && (
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}
                className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 font-medium">
                <Sparkles className="w-2.5 h-2.5" /> started
              </motion.span>
            )}
          </div>
        </div>
      </div>

      {/* Pending tasks — stagger + due dots */}
      {pending.length > 0 && (
        <div className="space-y-0.5 mb-3">
          {pending.slice(0, 4).map((t, idx) => {
            const dueDot = getDueDot(t.due_date)
            const isCompleting = completing.has(t.id)
            return (
              <motion.button key={t.id} onClick={() => handleComplete(t.id)}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.04, duration: 0.25 }}
                whileTap={{ scale: 0.97 }}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/10 dark:hover:bg-white/[0.04] hover:pl-3 transition-all text-left group">
                {isCompleting ? (
                  <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="shrink-0">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  </motion.span>
                ) : (
                  <Circle className="w-3.5 h-3.5 text-text-muted shrink-0 group-hover:text-primary group-hover:scale-110 transition-all" />
                )}
                <span className={`text-xs truncate flex-1 transition-all ${isCompleting ? "text-text-muted line-through" : "text-text-primary"}`}>
                  {t.title}
                </span>
                {dueDot && (
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dueDot.color}`} title={dueDot.label} />
                )}
                {t.priority === "high" && !isCompleting && (
                  <span className="text-[9px] text-red-500/70 font-medium shrink-0">high</span>
                )}
              </motion.button>
            )
          })}
          {pending.length > 4 && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="text-[10px] text-text-muted pl-2">+{pending.length - 4} more</motion.p>
          )}
        </div>
      )}

      {/* Recent done — last 2 */}
      {done.length > 0 && done.length <= 5 && (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mb-2 px-2 py-1.5 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
          <p className="text-[9px] text-emerald-600/70 dark:text-emerald-400/70 font-medium mb-0.5 uppercase tracking-wider">Recently Done</p>
          {done.slice(-2).map((t) => (
            <div key={t.id} className="flex items-center gap-1.5 py-0.5">
              <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />
              <span className="text-[11px] text-text-muted line-through truncate">{t.title}</span>
            </div>
          ))}
        </motion.div>
      )}

      {/* Quick add */}
      <div className="flex gap-1.5">
        <input value={quickTitle} onChange={(e) => setQuickTitle(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
          placeholder={placeholder}
          className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 focus:ring-2 focus:ring-primary/20 transition-all" />
        {(["high", "medium", "low"] as const).map((p) => (
          <button key={p} onClick={() => setQuickPriority(p)}
            className={`w-7 h-7 rounded-full flex items-center justify-center text-[9px] font-semibold uppercase tracking-wider transition-all ${
              quickPriority === p
                ? p === "high" ? "bg-red-500/15 text-red-500 border border-red-500/30 shadow-sm"
                : p === "medium" ? "bg-yellow-500/15 text-yellow-500 border border-yellow-500/30 shadow-sm"
                : "bg-white/20 dark:bg-white/[0.08] text-text-primary border border-border/50"
                : "bg-white/10 dark:bg-white/[0.04] text-text-muted border border-transparent"
            }`}>{p === "high" ? "H" : p === "medium" ? "M" : "L"}</button>
        ))}
        <button onClick={handleQuickAdd} disabled={!quickTitle.trim() || createMut.isPending}
          className="w-8 h-8 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0 shadow-lg">
          <Plus className="w-4 h-4" />
        </button>
      </div>
    </WidgetCard>
  )
}
