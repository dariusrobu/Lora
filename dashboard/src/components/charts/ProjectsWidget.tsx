import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchProjects, createProject } from "../../api/queries/projects"
import { WidgetCard } from "./WidgetCard"
import { FolderKanban, Plus } from "lucide-react"

interface Props { onExpand?: () => void }

export function ProjectsWidget({ onExpand }: Props) {
  const [quickName, setQuickName] = useState("")
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

  const active = projects?.filter((p) => p.status === "active") ?? []
  const top3 = active.slice(0, 3)
  const hasData = top3.length > 0

  const handleQuickAdd = () => {
    if (!quickName.trim() || createMut.isPending) return
    createMut.mutate({ name: quickName.trim() })
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
      emptyMessage="No active projects"
      emptyCTA={
        <div className="flex gap-1.5 w-full max-w-64">
          <input value={quickName} onChange={(e) => setQuickName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
            placeholder="Project name..." autoFocus
            className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors" />
          <button onClick={handleQuickAdd} disabled={!quickName.trim() || createMut.isPending}
            className="w-8 h-8 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0">
            <Plus className="w-4 h-4" />
          </button>
        </div>
      }
    >
      {/* Hero — count */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl font-bold text-text-primary">{active.length}</span>
        <span className="text-xs text-text-secondary">active projects</span>
      </div>

      {/* Top 3 projects with progress */}
      <div className="space-y-2.5">
        {top3.map((p, idx) => (
          <motion.div key={p.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05 }}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-text-primary truncate">{p.name}</span>
              <span className="text-[10px] text-text-muted tabular-nums ml-2">{p.progress_pct}%</span>
            </div>
            <div className="h-1.5 bg-white/40 dark:bg-white/[0.06] rounded-full overflow-hidden">
              <div className="h-full bg-violet-500 rounded-full transition-all duration-500"
                style={{ width: `${p.progress_pct}%` }} />
            </div>
            {p.completed_tasks !== undefined && (
              <p className="text-[9px] text-text-muted mt-0.5">{p.completed_tasks}/{p.task_count} tasks</p>
            )}
          </motion.div>
        ))}
      </div>

      {/* Quick add */}
      <div className="flex gap-1.5 mt-3">
        <input value={quickName} onChange={(e) => setQuickName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
          placeholder="Quick add project..."
          className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors" />
        <button onClick={handleQuickAdd} disabled={!quickName.trim() || createMut.isPending}
          className="w-8 h-8 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0">
          <Plus className="w-4 h-4" />
        </button>
      </div>
    </WidgetCard>
  )
}
