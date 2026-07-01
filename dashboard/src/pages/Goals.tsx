import { useState, useMemo, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import {
  fetchGoals,
  createGoal,
  completeGoal,
  deleteGoal,
  updateGoal,
  addSubtask,
  toggleSubtask,
  deleteSubtask,
} from "../api/queries/goals"
import { Card, Spinner, Modal } from "../components/ui"
import { Plus, Trash2, Search, CheckCircle2, Circle, ChevronDown, ChevronRight, X, Calendar } from "lucide-react"
import type { Goal, GoalTask } from "../types"

const horizonStyles: Record<string, { label: string; color: string }> = {
  short: { label: "S", color: "text-blue-400" },
  mid: { label: "M", color: "text-indigo-400" },
  long: { label: "L", color: "text-amber-400" },
}

function getDeadlineInfo(deadline: string | undefined) {
  if (!deadline) return null
  const t = new Date()
  t.setHours(0, 0, 0, 0)
  const d = new Date(deadline + "T00:00:00")
  const diff = (d.getTime() - t.getTime()) / (1000 * 60 * 60 * 24)
  if (diff < 0) return { label: `${Math.abs(Math.round(diff))}d`, color: "text-red-400" }
  if (diff === 0) return { label: "Today", color: "text-yellow-400" }
  if (diff <= 7) return { label: `${Math.round(diff)}d`, color: "text-orange-400" }
  return { label: deadline, color: "text-text-muted" }
}

interface Section {
  label: string
  goals: Goal[]
  color?: string
}

function groupGoals(goals: Goal[], groupBy: string): Section[] {
  switch (groupBy) {
    case "horizon": {
      const order = ["short", "mid", "long"]
      return order.map((h) => ({
        label: h === "short" ? "Short-term" : h === "mid" ? "Mid-term" : "Long-term",
        color: horizonStyles[h]?.color,
        goals: goals.filter((g) => g.time_horizon === h),
      })).filter((s) => s.goals.length > 0)
    }
    case "category": {
      const map = new Map<string, Goal[]>()
      goals.forEach((g) => {
        const key = g.category ?? "Other"
        if (!map.has(key)) map.set(key, [])
        map.get(key)!.push(g)
      })
      return Array.from(map.entries()).map(([label, goals]) => ({ label, goals }))
    }
    default:
      return [{ label: "", goals }]
  }
}

export default function Goals() {
  const [filter, setFilter] = useState<"all" | "active" | "done">("all")
  const [groupBy, setGroupBy] = useState<string>("horizon")
  const [search, setSearch] = useState("")
  const [showGroupMenu, setShowGroupMenu] = useState(false)

  const [expandedId, setExpandedId] = useState<number | null>(null)

  const [showModal, setShowModal] = useState(false)
  const [formTitle, setFormTitle] = useState("")
  const [formHorizon, setFormHorizon] = useState<"short" | "mid" | "long">("mid")
  const [formDeadline, setFormDeadline] = useState("")
  const [formCategory, setFormCategory] = useState("")
  const formRef = useRef<HTMLInputElement>(null)

  const [subInput, setSubInput] = useState("")
  const [subGoalId, setSubGoalId] = useState<number | null>(null)
  const subRef = useRef<HTMLInputElement>(null)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editValue, setEditValue] = useState("")
  const editRef = useRef<HTMLInputElement>(null)

  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: ["goals"] })

  const { data: goals, isLoading } = useQuery({
    queryKey: ["goals"],
    queryFn: fetchGoals,
  })

  const createMut = useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      invalidate()
      setShowModal(false)
      setFormTitle("")
      setFormHorizon("mid")
      setFormDeadline("")
      setFormCategory("")
    },
  })

  const completeMut = useMutation({
    mutationFn: completeGoal,
    onSuccess: invalidate,
  })

  const deleteMut = useMutation({
    mutationFn: deleteGoal,
    onSuccess: invalidate,
  })

  const updateMut = useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: Partial<Goal> }) => updateGoal(id, updates),
    onSuccess: invalidate,
  })

  const addSubMut = useMutation({
    mutationFn: ({ goalId, title }: { goalId: number; title: string }) => addSubtask(goalId, title),
    onSuccess: invalidate,
  })

  const toggleSubMut = useMutation({
    mutationFn: toggleSubtask,
    onSuccess: invalidate,
  })

  const deleteSubMut = useMutation({
    mutationFn: deleteSubtask,
    onSuccess: invalidate,
  })

  const filtered = useMemo(() => {
    let result = goals ?? []
    if (filter === "active") result = result.filter((g) => g.status !== "done")
    else if (filter === "done") result = result.filter((g) => g.status === "done")
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter((g) => g.title.toLowerCase().includes(q))
    }
    return result
  }, [goals, filter, search])

  const activeCount = (goals ?? []).filter((g) => g.status !== "done").length
  const doneCount = (goals ?? []).filter((g) => g.status === "done").length
  const avgProgress = goals && goals.length > 0
    ? Math.round(goals.reduce((s, g) => s + (g.progress ?? 0), 0) / goals.length)
    : 0

  const sections = useMemo(() => groupGoals(filtered, groupBy), [filtered, groupBy])

  const filters = ["all", "active", "done"] as const
  const groupOptions = [
    { key: "horizon", label: "Horizon" },
    { key: "category", label: "Category" },
    { key: "none", label: "None" },
  ] as const

  const openModal = () => {
    setFormTitle("")
    setFormHorizon("mid")
    setFormDeadline("")
    setFormCategory("")
    setShowModal(true)
    setTimeout(() => formRef.current?.focus(), 100)
  }

  const handleCreate = () => {
    if (!formTitle.trim() || createMut.isPending) return
    const payload: Record<string, string> = { title: formTitle.trim(), time_horizon: formHorizon }
    if (formDeadline) payload.deadline = formDeadline
    if (formCategory.trim()) payload.category = formCategory.trim()
    createMut.mutate(payload)
  }

  const startEdit = (goal: Goal) => {
    setEditingId(goal.id)
    setEditValue(goal.title)
    setTimeout(() => editRef.current?.focus(), 10)
  }

  const saveEdit = (goalId: number) => {
    if (editValue.trim() && editValue.trim() !== goals?.find((g) => g.id === goalId)?.title) {
      updateMut.mutate({ id: goalId, updates: { title: editValue.trim() } })
    }
    setEditingId(null)
  }

  const toggleExpanded = (goalId: number) => {
    setExpandedId(expandedId === goalId ? null : goalId)
  }

  const startSubAdd = (goalId: number) => {
    setSubGoalId(goalId)
    setSubInput("")
    setTimeout(() => subRef.current?.focus(), 10)
  }

  const handleAddSubtask = () => {
    if (!subInput.trim() || addSubMut.isPending || subGoalId === null) return
    addSubMut.mutate({ goalId: subGoalId, title: subInput.trim() })
    setSubInput("")
  }

  if (isLoading) return <Spinner className="py-12" />

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div>
          <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-bold text-text-primary">Goals</h1>
        <button onClick={openModal}
          className="w-9 h-9 rounded-full bg-emerald-500 text-white shadow-sm flex items-center justify-center hover:brightness-110 transition-all"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {/* Progress bar */}
      {(goals ?? []).length > 0 && (
        <div className="mb-5">
          <div className="flex justify-between text-xs text-text-secondary mb-1.5">
            <span>{activeCount} active · {doneCount} done</span>
            <span>{avgProgress}% avg</span>
          </div>
          <div className="h-1 bg-surface rounded-full overflow-hidden">
            <div className="h-full bg-violet-500 rounded-full transition-all duration-500" style={{ width: `${avgProgress}%` }} />
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search goals..."
          className="w-full bg-surface border border-border rounded-xl py-2.5 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
        />
      </div>

      {/* Segmented control + group dropdown */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex p-0.5 rounded-full bg-surface border border-border">
          {filters.map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                  filter === f
                      ? "bg-white/10 dark:bg-white/[0.08] font-semibold text-text-primary"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {f === "all" ? "All" : f === "active" ? "Active" : "Done"}
            </button>
          ))}
        </div>

        <div className="relative">
          <button onClick={() => setShowGroupMenu(!showGroupMenu)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-surface border border-transparent hover:border-border transition-all"
          >
            {groupOptions.find((g) => g.key === groupBy)?.label ?? "Group"}
            <ChevronDown className="w-3 h-3" />
          </button>
          {showGroupMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowGroupMenu(false)} />
              <div className="absolute right-0 top-full mt-1 z-20 min-w-32 bg-bg border border-border rounded-xl shadow-apple-heavy dark:shadow-apple-dark py-1">
                {groupOptions.map((g) => (
                  <button key={g.key} onClick={() => { setGroupBy(g.key); setShowGroupMenu(false) }}
                    className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                      groupBy === g.key
                        ? "text-primary font-medium"
                        : "text-text-secondary hover:text-text-primary hover:bg-surface"
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* New Goal Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="New Goal">
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Title</label>
            <input ref={formRef} value={formTitle} onChange={(e) => setFormTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleCreate() }}
              placeholder="What's your goal?"
              className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Time Horizon</label>
            <div className="flex gap-1.5">
              {([{ key: "short", label: "Short" }, { key: "mid", label: "Mid" }, { key: "long", label: "Long" }] as const).map(({ key, label }) => (
                <button key={key} onClick={() => setFormHorizon(key)}
                  className={`flex-1 py-2 rounded-xl text-xs font-medium capitalize transition-all ${
                    formHorizon === key
                      ? key === "short"
                        ? "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                        : key === "mid"
                          ? "bg-white/10 dark:bg-white/[0.08] font-semibold text-text-primary border border-border"
                          : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                      : "bg-surface text-text-muted border border-transparent hover:border-border"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Deadline</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
              <input type="date" value={formDeadline} onChange={(e) => setFormDeadline(e.target.value)}
                className="w-full bg-surface border border-border rounded-xl pl-9 pr-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary/30 transition-all [color-scheme:var(--color-scheme)]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Category</label>
            <input value={formCategory} onChange={(e) => setFormCategory(e.target.value)}
              placeholder="e.g. Skills, Health, Finance..."
              className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
            />
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={() => setShowModal(false)}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-surface text-text-secondary hover:text-text-primary border border-border transition-colors"
            >
              Cancel
            </button>
            <button onClick={handleCreate} disabled={!formTitle.trim() || createMut.isPending}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-blue-600 text-white disabled:opacity-40 transition-all"
            >
              {createMut.isPending ? <Spinner size="sm" /> : "Add Goal"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Goals list */}
      {sections.length === 0 ? (
        <Card><p className="text-sm text-text-muted text-center py-8">No goals found</p></Card>
      ) : (
        <div className="space-y-5">
          {sections.map((section) => (
            <div key={section.label}>
              {section.label && (
                <div className="flex items-center gap-2 mb-2 px-1">
                  <span className={`text-xs font-semibold uppercase tracking-wider ${section.color ?? "text-text-muted"}`}>
                    {section.label}
                  </span>
                  <span className="text-xs text-text-muted">· {section.goals.length}</span>
                  <div className="flex-1 h-px bg-border" />
                </div>
              )}
              <div className="space-y-1">
                <AnimatePresence>
                  {section.goals.map((goal) => {
                    const isExpanded = expandedId === goal.id
                    const hc = horizonStyles[goal.time_horizon]
                    const deadlineInfo = getDeadlineInfo(goal.deadline)
                    const tasks = goal.tasks ?? []
                    const totalSub = tasks.length
                    const doneSub = tasks.filter((t) => t.is_completed).length

                    return (
                      <motion.div key={goal.id} layout initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}>
                        <div className={`rounded-2xl overflow-hidden ${goal.status === "done" ? "opacity-60" : ""} ${isExpanded ? "bg-surface border border-border" : ""}`}>
                          {/* Header row */}
                          <div className={`flex items-center gap-2.5 py-2 px-3 rounded-xl transition-all ${!isExpanded ? "hover:bg-surface" : ""}`}>
                            <button onClick={() => toggleExpanded(goal.id)}
                              className="shrink-0 text-text-muted hover:text-text-secondary transition-colors"
                            >
                              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            </button>

                            <button onClick={() => {
                              if (goal.status === "done") updateMut.mutate({ id: goal.id, updates: { status: "active", progress: 0 } })
                              else completeMut.mutate(goal.id)
                            }}>
                              {goal.status === "done" ? (
                                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                              ) : (
                                <Circle className="w-5 h-5 text-text-muted hover:text-text-secondary transition-colors" />
                              )}
                            </button>

                            <div className="flex-1 min-w-0">
                              {editingId === goal.id ? (
                                <input ref={editRef} value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onBlur={() => saveEdit(goal.id)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") saveEdit(goal.id)
                                    if (e.key === "Escape") setEditingId(null)
                                  }}
                                  className="w-full bg-surface border border-border rounded-lg px-2 py-0.5 text-sm text-text-primary outline-none"
                                  onClick={(e) => e.stopPropagation()}
                                />
                              ) : (
                                <button onClick={() => startEdit(goal)}
                                  className={`text-sm text-left w-full truncate font-medium ${
                                    goal.status === "done" ? "line-through text-text-muted" : "text-text-primary"
                                  }`}
                                >
                                  {goal.title}
                                </button>
                              )}
                            </div>

                            <span className={`text-[10px] font-semibold uppercase tracking-wider ${hc?.color}`}>{hc?.label}</span>

                            {deadlineInfo && (
                              <span className={`text-xs shrink-0 ${deadlineInfo.color}`}>{deadlineInfo.label}</span>
                            )}

                            <span className="text-xs font-semibold text-text-primary shrink-0 tabular-nums">
                              {goal.progress}%
                            </span>

                            <button onClick={() => deleteMut.mutate(goal.id)}
                              className="text-text-muted hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          {/* Progress bar */}
                          <div className="px-3 pb-2">
                            <div className="h-[3px] bg-white/20 dark:bg-white/[0.08] rounded-full overflow-hidden">
                              <div className="h-full bg-violet-500 rounded-full transition-all duration-700" style={{ width: `${goal.progress}%` }} />
                            </div>
                          </div>

                          {/* Expanded: description + subtasks */}
                          {isExpanded && (
                            <div className="px-3 pb-3 space-y-2 border-t border-border pt-2">
                              {goal.description && (
                                <p className="text-xs text-text-muted italic">{goal.description}</p>
                              )}
                              {goal.category && (
                                <span className="text-[10px] text-text-muted uppercase tracking-wider">#{goal.category}</span>
                              )}

                              {/* Subtasks */}
                              {totalSub > 0 && (
                                <div className="text-[10px] text-text-muted">{doneSub}/{totalSub} tasks</div>
                              )}
                              <div className="space-y-0.5">
                                {tasks.map((st: GoalTask) => (
                                  <div key={st.id} className="flex items-center gap-2 py-0.5 group">
                                    <button onClick={() => toggleSubMut.mutate(st.id)}>
                                      {st.is_completed ? (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                      ) : (
                                        <Circle className="w-3.5 h-3.5 text-text-muted hover:text-text-secondary transition-colors" />
                                      )}
                                    </button>
                                    <span className={`text-xs flex-1 ${st.is_completed ? "line-through text-text-muted" : "text-text-primary"}`}>
                                      {st.title}
                                    </span>
                                    <button onClick={() => deleteSubMut.mutate(st.id)}
                                      className="text-text-muted hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                                    >
                                      <X className="w-3 h-3" />
                                    </button>
                                  </div>
                                ))}
                              </div>

                              {/* Add subtask input */}
                              {subGoalId === goal.id ? (
                                <div className="flex gap-2 pt-1">
                                  <input ref={subRef} value={subInput}
                                    onChange={(e) => setSubInput(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === "Enter") handleAddSubtask() }}
                                    onBlur={() => setTimeout(() => setSubGoalId(null), 200)}
                                    placeholder="Add sub-task..."
                                    className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-lg px-2.5 py-1.5 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                                  />
                                  <button onClick={handleAddSubtask} disabled={!subInput.trim() || addSubMut.isPending}
                                     className="w-7 h-7 rounded-full bg-sky-500 text-white flex items-center justify-center shrink-0 disabled:opacity-40 transition-opacity"
                                  >
                                    {addSubMut.isPending ? <Spinner size="sm" /> : <Plus className="w-3 h-3" />}
                                  </button>
                                </div>
                              ) : (
                                <button onClick={() => startSubAdd(goal.id)}
                                  className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary transition-colors"
                                >
                                  <Plus className="w-3 h-3" />
                                  Add sub-task
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )
                  })}
                </AnimatePresence>
              </div>
            </div>
          ))}
        </div>
      )}
        </div>
      </div>
    </div>
  )
}
