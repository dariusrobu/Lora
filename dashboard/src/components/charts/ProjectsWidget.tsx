import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchProjects, createProject } from "../../api/queries/projects"
import { WidgetCard } from "./WidgetCard"
import { FolderKanban, Plus, CheckCircle2, TrendingUp, Calendar, ArrowUpRight } from "lucide-react"

interface Props { onExpand?: () => void }

export function ProjectsWidget({ onExpand }: Props) {
  const [quickName, setQuickName] = useState("")
  const [quickPriority, setQuickPriority] = useState<"high" | "medium" | "low">("medium")
  const qc = useQueryClient()

  const { data: projects, isLoading, isError, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const createMut = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] })
      setQuickName("")
    },
  })

  const active = useMemo(() => projects?.filter((p) => p.status === "active") ?? [], [projects])
  const completed = useMemo(() => projects?.filter((p) => p.status === "completed") ?? [], [projects])
  
  const avgProgress = useMemo(() => {
    if (active.length === 0) return 0
    const total = active.reduce((acc, p) => acc + (p.progress_pct ?? 0), 0)
    return Math.round(total / active.length)
  }, [active])

  const totalActiveTasks = useMemo(() => {
    return active.reduce((acc, p) => acc + (p.pending_tasks ?? 0), 0)
  }, [active])

  const heroProject = active[0] ?? null
  const otherProjects = active.slice(1, 4)
  const hasData = active.length > 0 || (projects?.length ?? 0) > 0

  const handleQuickAdd = () => {
    if (!quickName.trim() || createMut.isPending) return
    createMut.mutate({ name: quickName.trim(), priority: quickPriority })
  }

  return (
    <WidgetCard
      icon={<FolderKanban className="w-4 h-4" />}
      label="Projects"
      linkTo="/projects"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="Niciun proiect activ"
      emptyCTA={
        <div className="flex gap-2 w-full max-w-xs mt-2">
          <input
            value={quickName}
            onChange={(e) => setQuickName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
            placeholder="Nume proiect nou..."
            autoFocus
            className="flex-1 bg-white/[0.03] border border-white/[0.08] focus:border-indigo-400/40 rounded-xl py-2 px-3 text-xs text-white placeholder:text-zinc-500 outline-none transition-all"
          />
          <button
            onClick={handleQuickAdd}
            disabled={!quickName.trim() || createMut.isPending}
            className="px-3 py-2 rounded-xl bg-gradient-to-tr from-primary to-accent text-white font-bold text-xs disabled:opacity-40 transition-all flex items-center justify-center shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      }
    >
      {/* 3 Prominent Metrics */}
      <div className="grid grid-cols-3 gap-3 p-3 rounded-2xl bg-white/[0.015] border border-white/[0.04] mb-4 divide-x divide-white/[0.06]">
        {/* Active Projects */}
        <div className="flex flex-col items-center sm:items-start sm:pl-2">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <FolderKanban className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Active</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-white tabular-nums tracking-tight">
            {active.length}
          </span>
        </div>

        {/* Average Progress */}
        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Medie</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-emerald-400 tabular-nums tracking-tight">
            {avgProgress}%
          </span>
        </div>

        {/* Pending Tasks in Projects */}
        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <CheckCircle2 className="w-3.5 h-3.5 text-violet-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Task-uri</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-violet-300 tabular-nums tracking-tight">
            {totalActiveTasks}
          </span>
        </div>
      </div>

      {/* Hero Project Card */}
      {heroProject && (
        <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.05] mb-4 group hover:border-indigo-500/20 transition-all">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-400">
                  Proiect Prioritar
                </span>
                {heroProject.priority === "high" && (
                  <span className="px-2 py-0.2 rounded-full bg-rose-500/15 border border-rose-500/25 text-rose-400 text-[9px] font-bold uppercase tracking-wider">
                    urgent
                  </span>
                )}
                {heroProject.category && (
                  <span className="px-2 py-0.2 rounded-full bg-white/[0.05] text-zinc-400 text-[9px] font-medium">
                    {heroProject.category}
                  </span>
                )}
              </div>
              <h4 className="text-base font-bold text-white truncate tracking-tight group-hover:text-indigo-200 transition-colors">
                {heroProject.name}
              </h4>
            </div>

            {/* Percentage Value */}
            <span className="text-2xl sm:text-3xl font-black text-text-primary tabular-nums shrink-0">
              {heroProject.progress_pct ?? 0}%
            </span>
          </div>

          {/* Large Fluid Progress Bar */}
          <div className="space-y-1.5 my-3">
            <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden p-0.5">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${heroProject.progress_pct ?? 0}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 shadow-[0_0_12px_rgba(99,102,241,0.5)]"
              />
            </div>
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
              <span>{heroProject.completed_tasks ?? 0} din {heroProject.task_count ?? 0} task-uri finalizate</span>
              {heroProject.deadline && (
                <span className="flex items-center gap-1 text-zinc-400">
                  <Calendar className="w-3 h-3 text-indigo-400" />
                  {heroProject.deadline}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Other Active Projects List */}
      {otherProjects.length > 0 && (
        <div className="space-y-2 mb-4">
          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 px-1 block">
            Alte Proiecte în Lucru ({otherProjects.length})
          </span>
          {otherProjects.map((p, idx) => (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04 }}
              className="flex items-center justify-between p-2.5 rounded-xl hover:bg-white/[0.035] border border-transparent hover:border-white/[0.04] transition-all"
            >
              <div className="min-w-0 flex-1 mr-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-zinc-200 truncate">{p.name}</span>
                  <span className="text-[11px] font-bold text-zinc-400 tabular-nums ml-2">
                    {p.progress_pct ?? 0}%
                  </span>
                </div>
                <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all duration-500"
                    style={{ width: `${p.progress_pct ?? 0}%` }}
                  />
                </div>
              </div>
              <span className="text-[10px] text-zinc-500 tabular-nums shrink-0">
                {p.completed_tasks ?? 0}/{p.task_count ?? 0}
              </span>
            </motion.div>
          ))}
        </div>
      )}

      {/* Quick Add Bar (Linear Style) */}
      <div className="flex items-center gap-2 pt-2 border-t border-white/[0.05]">
        <input
          value={quickName}
          onChange={(e) => setQuickName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
          placeholder="Adaugă proiect rapid..."
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
          disabled={!quickName.trim() || createMut.isPending}
          whileTap={{ scale: 0.95 }}
          className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary to-accent text-white disabled:opacity-30 transition-all flex items-center justify-center shrink-0 shadow-[0_2px_12px_rgba(99,102,241,0.3)] hover:scale-105"
        >
          <Plus className="w-4 h-4" />
        </motion.button>
      </div>
    </WidgetCard>
  )
}
