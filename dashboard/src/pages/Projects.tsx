import { useState, useMemo, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import {
  fetchProjects,
  createProject,
  updateProject,
  deleteProject,
} from "../api/queries/projects"
import { createTask as apiCreateTask, updateTask as apiUpdateTask } from "../api/queries/tasks"
import { createNote as apiCreateNote, deleteNote as apiDeleteNote } from "../api/queries/notes"
import { Card, Spinner, Modal } from "../components/ui"
import {
  Plus, Trash2, Search, CheckCircle2, Circle, ChevronDown, ChevronRight,
  FolderKanban, FileText, X, AlertCircle, Calendar,
} from "lucide-react"
import type { Project, ProjectTask, ProjectNote } from "../types"

const priorityColors: Record<string, { label: string; color: string; bg: string }> = {
  high: { label: "High", color: "text-red-400", bg: "bg-red-500/15" },
  medium: { label: "Medium", color: "text-yellow-400", bg: "bg-yellow-500/15" },
  low: { label: "Low", color: "text-text-secondary", bg: "bg-surface" },
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
  return { label: deadline, color: "text-text-secondary" }
}

interface Section {
  label: string
  projects: Project[]
  color?: string
}

function groupProjects(projects: Project[], groupBy: string): Section[] {
  switch (groupBy) {
    case "priority":
      return (["high", "medium", "low"] as const).map((p) => ({
        label: priorityColors[p]?.label ?? p,
        color: priorityColors[p]?.color,
        projects: projects.filter((x) => x.priority === p),
      })).filter((s) => s.projects.length > 0)
    case "status": {
      const map = new Map<string, Project[]>()
      projects.forEach((p) => {
        const key = p.status === "completed" || p.status === "done" ? "Completed" : p.status === "paused" ? "Paused" : "Active"
        if (!map.has(key)) map.set(key, [])
        map.get(key)!.push(p)
      })
      return Array.from(map.entries()).map(([label, projects]) => ({ label, projects }))
    }
    case "category": {
      const map = new Map<string, Project[]>()
      projects.forEach((p) => {
        const key = p.category ?? "Other"
        if (!map.has(key)) map.set(key, [])
        map.get(key)!.push(p)
      })
      return Array.from(map.entries()).map(([label, projects]) => ({ label, projects }))
    }
    default:
      return [{ label: "", projects }]
  }
}

export default function Projects() {
  const [filter, setFilter] = useState<"all" | "active" | "completed">("all")
  const [groupBy, setGroupBy] = useState<string>("category")
  const [search, setSearch] = useState("")
  const [showGroupMenu, setShowGroupMenu] = useState(false)

  const [showModal, setShowModal] = useState(false)
  const [formName, setFormName] = useState("")
  const [formPriority, setFormPriority] = useState<"low" | "medium" | "high">("medium")
  const [formCategory, setFormCategory] = useState("")
  const [formHasDeadline, setFormHasDeadline] = useState(false)
  const [formDeadline, setFormDeadline] = useState("")
  const [formDescription, setFormDescription] = useState("")
  const formRef = useRef<HTMLInputElement>(null)

  const [expandedId, setExpandedId] = useState<number | null>(null)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editValue, setEditValue] = useState("")
  const editRef = useRef<HTMLInputElement>(null)

  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  const [taskInput, setTaskInput] = useState("")
  const [taskProjectId, setTaskProjectId] = useState<number | null>(null)
  const taskRef = useRef<HTMLInputElement>(null)
  const [noteInput, setNoteInput] = useState("")
  const [noteProjectId, setNoteProjectId] = useState<number | null>(null)
  const noteRef = useRef<HTMLInputElement>(null)

  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: ["projects"] })

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  })

  const createMut = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      invalidate()
      setShowModal(false)
      setFormName("")
      setFormPriority("medium")
      setFormCategory("")
      setFormDeadline("")
      setFormDescription("")
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteProject,
    onSuccess: invalidate,
  })

  const updateMut = useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: Partial<Project> }) => updateProject(id, updates),
    onSuccess: invalidate,
  })

  const addTaskMut = useMutation({
    mutationFn: ({ project_id, title }: { project_id: number; title: string }) =>
      apiCreateTask({ title, project_id, priority: "medium" }),
    onSuccess: () => { invalidate(); setTaskInput("") },
  })

  const toggleTaskMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiUpdateTask(id, { status: status === "done" ? "pending" : "done" } as any),
    onSuccess: invalidate,
  })

  const addNoteMut = useMutation({
    mutationFn: ({ project_id, content }: { project_id: number; content: string }) =>
      apiCreateNote({ content, project_id, type: "note" }),
    onSuccess: () => { invalidate(); setNoteInput("") },
  })

  const deleteNoteMut = useMutation({
    mutationFn: apiDeleteNote,
    onSuccess: invalidate,
  })

  const filtered = useMemo(() => {
    let result = projects ?? []
    if (filter === "active") result = result.filter((p) => p.status !== "done" && p.status !== "completed")
    else if (filter === "completed") result = result.filter((p) => p.status === "done" || p.status === "completed")
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter((p) => p.name.toLowerCase().includes(q) || (p.description ?? "").toLowerCase().includes(q))
    }
    return result
  }, [projects, filter, search])

  const activeCount = (projects ?? []).filter((p) => p.status !== "done" && p.status !== "completed").length
  const doneCount = (projects ?? []).filter((p) => p.status === "done" || p.status === "completed").length
  const avgProgress = projects && projects.length > 0
    ? Math.round(projects.reduce((s, p) => s + (p.progress_pct ?? 0), 0) / projects.length)
    : 0

  const sections = useMemo(() => groupProjects(filtered, groupBy), [filtered, groupBy])

  const filters = ["all", "active", "completed"] as const
  const groupOptions = [
    { key: "priority", label: "Priority" },
    { key: "status", label: "Status" },
    { key: "category", label: "Category" },
    { key: "none", label: "None" },
  ] as const

  const openModal = () => {
    setFormName("")
    setFormPriority("medium")
    setFormCategory("")
    setFormHasDeadline(false)
    setFormDeadline("")
    setFormDescription("")
    setShowModal(true)
    setTimeout(() => formRef.current?.focus(), 100)
  }

  const handleCreate = () => {
    if (!formName.trim() || createMut.isPending) return
    const payload: Record<string, string> = { name: formName.trim(), priority: formPriority }
    if (formCategory.trim()) payload.category = formCategory.trim()
    if (formHasDeadline && formDeadline) payload.deadline = formDeadline
    if (formDescription.trim()) payload.description = formDescription.trim()
    createMut.mutate(payload)
  }

  const startEdit = (project: Project) => {
    setEditingId(project.id)
    setEditValue(project.name)
    setTimeout(() => editRef.current?.focus(), 10)
  }

  const saveEdit = (projectId: number) => {
    if (editValue.trim() && editValue.trim() !== projects?.find((p) => p.id === projectId)?.name) {
      updateMut.mutate({ id: projectId, updates: { name: editValue.trim() } })
    }
    setEditingId(null)
  }

  const toggleExpanded = (projectId: number) => {
    setExpandedId(expandedId === projectId ? null : projectId)
  }

  const handleToggleStatus = (project: Project) => {
    const isDone = project.status === "done" || project.status === "completed"
    updateMut.mutate({ id: project.id, updates: { status: isDone ? "active" : "completed" } })
  }

  if (isLoading) return <Spinner className="py-12" />

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div>
          <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-bold text-text-primary">Projects</h1>
        <button onClick={openModal}
          className="w-9 h-9 rounded-full bg-emerald-500 text-white shadow-sm flex items-center justify-center hover:brightness-110 transition-all"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {/* Progress bar */}
      {(projects ?? []).length > 0 && (
        <div className="mb-5">
          <div className="flex justify-between text-xs text-text-secondary mb-1.5">
            <span>{activeCount} active · {doneCount} completed</span>
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
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search projects..."
          className="w-full bg-surface border border-border rounded-xl py-2.5 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
        />
      </div>

      {/* Segmented control + group dropdown */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex p-0.5 rounded-full bg-surface border border-border">
          {filters.map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                 filter === f ? "bg-white/10 dark:bg-white/[0.08] font-semibold text-text-primary" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {f === "all" ? "All" : f === "active" ? "Active" : "Completed"}
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
                      groupBy === g.key ? "text-primary font-medium" : "text-text-secondary hover:text-text-primary hover:bg-surface"
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

      {/* Project list */}
      {sections.length === 0 ? (
        <Card><p className="text-sm text-text-muted text-center py-8">No projects found</p></Card>
      ) : (
        <div className="space-y-5">
          {sections.map((section) => (
            <div key={section.label}>
              {section.label && (
                <div className="flex items-center gap-2 mb-2 px-1">
                  <span className={`text-xs font-semibold uppercase tracking-wider ${section.color ?? "text-text-muted"}`}>
                    {section.label}
                  </span>
                  <span className="text-xs text-text-muted">· {section.projects.length}</span>
                  <div className="flex-1 h-px bg-border" />
                </div>
              )}
              <div className="space-y-1">
                <AnimatePresence>
                  {section.projects.map((project) => {
                    const isExpanded = expandedId === project.id
                    const pc = priorityColors[project.priority]
                    const deadlineInfo = getDeadlineInfo(project.deadline)
                    const pct = project.progress_pct ?? (
                      project.task_count && project.task_count > 0
                        ? Math.round(((project.completed_tasks ?? 0) / project.task_count) * 100)
                        : 0
                    )
                    const tasks = project.tasks ?? []
                    const notes = project.notes ?? []

                    return (
                      <motion.div key={project.id} layout initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}>
                        <div className={`rounded-2xl overflow-hidden ${project.status === "completed" || project.status === "done" ? "opacity-60" : ""} ${isExpanded ? "bg-surface border border-border" : ""}`}>
                          {/* Header */}
                          <div className={`flex items-center gap-2.5 py-2 px-3 rounded-xl transition-all ${!isExpanded ? "hover:bg-surface" : ""}`}>
                            <button onClick={() => toggleExpanded(project.id)}
                              className="shrink-0 text-text-muted hover:text-text-secondary transition-colors"
                            >
                              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            </button>

                            <button onClick={() => handleToggleStatus(project)}>
                              {project.status === "done" || project.status === "completed" ? (
                                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                              ) : (
                                <Circle className="w-5 h-5 text-text-muted hover:text-text-secondary transition-colors" />
                              )}
                            </button>

                            <FolderKanban className="w-4 h-4 text-primary shrink-0" />

                            <div className="flex-1 min-w-0">
                              {editingId === project.id ? (
                                <input ref={editRef} value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onBlur={() => saveEdit(project.id)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") saveEdit(project.id)
                                    if (e.key === "Escape") setEditingId(null)
                                  }}
                                  className="w-full bg-surface border border-border rounded-lg px-2 py-0.5 text-sm text-text-primary outline-none"
                                  onClick={(e) => e.stopPropagation()}
                                />
                              ) : (
                                <button onClick={() => startEdit(project)}
                                  className={`text-sm text-left w-full truncate font-medium ${
                                    project.status === "done" || project.status === "completed" ? "line-through text-text-muted" : "text-text-primary"
                                  }`}
                                >
                                  {project.name}
                                </button>
                              )}
                            </div>

                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${pc?.bg} ${pc?.color}`}>
                              {pc?.label ?? project.priority}
                            </span>

                            {project.status === "paused" && (
                              <span className="text-xs text-amber-400 bg-amber-500/15 px-2 py-0.5 rounded">Paused</span>
                            )}

                            {deadlineInfo && (
                              <span className={`text-xs shrink-0 ${deadlineInfo.color}`}>{deadlineInfo.label}</span>
                            )}

                            <span className="text-xs font-semibold text-primary shrink-0">{pct}%</span>

                            {confirmDeleteId === project.id ? (
                              <div className="flex gap-1 shrink-0">
                                <button onClick={() => deleteMut.mutate(project.id)}
                                  className="px-2 py-0.5 text-[10px] font-semibold bg-red-500/15 text-red-400 rounded"
                                >
                                  Yes
                                </button>
                                <button onClick={() => setConfirmDeleteId(null)}
                                  className="px-2 py-0.5 text-[10px] font-semibold bg-surface text-text-primary rounded"
                                >
                                  No
                                </button>
                              </div>
                            ) : (
                              <button onClick={() => setConfirmDeleteId(project.id)}
                                className="text-text-muted hover:text-red-500 transition-colors shrink-0"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>

                          {/* Progress bar */}
                          <div className="px-3 pb-2">
                            <div className="h-[3px] bg-white/20 dark:bg-white/[0.08] rounded-full overflow-hidden">
                              <div className="h-full bg-violet-500 rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
                            </div>
                          </div>

                          {/* Meta line */}
                          {!isExpanded && (
                            <div className="px-3 pb-2 flex items-center gap-2 text-[10px] text-text-muted">
                              {project.category && <span>{project.category}</span>}
                              {project.category && (project.task_count !== undefined) && <span>·</span>}
                              <span>{project.completed_tasks ?? 0}/{project.task_count ?? 0} tasks</span>
                              {(project.overdue_tasks ?? 0) > 0 && (
                                <span className="flex items-center gap-0.5 text-red-400">
                                  <AlertCircle className="w-3 h-3" />
                                  {project.overdue_tasks} overdue
                                </span>
                              )}
                            </div>
                          )}

                          {/* Expanded: description + tasks + notes */}
                          {isExpanded && (
                            <div className="px-3 pb-3 space-y-3 border-t border-border pt-2">
                              {project.description && (
                                <p className="text-xs text-text-muted italic leading-relaxed">{project.description}</p>
                              )}

                              {/* Tasks */}
                              <div>
                                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Tasks</div>
                                {tasks.length > 0 && (
                                  <div className="space-y-0.5 mb-2">
                                    {tasks.map((t: ProjectTask) => (
                                      <div key={t.id} className="flex items-center gap-2 py-0.5 group">
                                        <button onClick={() => toggleTaskMut.mutate({ id: t.id, status: t.status })}>
                                          {t.status === "done" ? (
                                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                          ) : (
                                            <Circle className="w-3.5 h-3.5 text-text-muted hover:text-text-secondary transition-colors" />
                                          )}
                                        </button>
                                        <span className={`text-xs flex-1 ${t.status === "done" ? "line-through text-text-muted" : "text-text-primary"}`}>
                                          {t.title}
                                        </span>
                                        <span className={`text-[10px] ${t.priority === "high" ? "text-red-400" : t.priority === "medium" ? "text-yellow-400" : "text-text-muted"}`}>
                                          {t.priority === "high" ? "H" : t.priority === "medium" ? "M" : "L"}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {taskProjectId === project.id ? (
                                  <div className="flex gap-2">
                                    <input ref={taskRef} value={taskInput} onChange={(e) => setTaskInput(e.target.value)}
                                      onKeyDown={(e) => { if (e.key === "Enter" && taskInput.trim()) addTaskMut.mutate({ project_id: project.id, title: taskInput.trim() }) }}
                                      onBlur={() => setTimeout(() => setTaskProjectId(null), 200)}
                                      placeholder="Add task..."
                                      className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-lg px-2.5 py-1.5 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                                    />
                                    <button onClick={() => { if (taskInput.trim()) addTaskMut.mutate({ project_id: project.id, title: taskInput.trim() }) }}
                                      disabled={!taskInput.trim() || addTaskMut.isPending}
                                      className="w-7 h-7 rounded-full bg-sky-500 text-white flex items-center justify-center shrink-0 disabled:opacity-40 transition-opacity"
                                    >
                                      {addTaskMut.isPending ? <Spinner size="sm" /> : <Plus className="w-3.5 h-3.5" />}
                                    </button>
                                  </div>
                                ) : (
                                  <button onClick={() => { setTaskProjectId(project.id); setTaskInput(""); setTimeout(() => taskRef.current?.focus(), 10) }}
                                    className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary transition-colors"
                                  >
                                    <Plus className="w-3 h-3" />
                                    Add task
                                  </button>
                                )}
                              </div>

                              {/* Notes */}
                              <div className="border-t border-border pt-2">
                                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Notes</div>
                                {notes.length > 0 && (
                                  <div className="space-y-1 mb-2">
                                    {notes.map((n: ProjectNote) => (
                                      <div key={n.id} className="flex items-start gap-2 group">
                                        <FileText className="w-3 h-3 text-text-muted mt-0.5 shrink-0" />
                                        <p className="text-xs text-text-secondary flex-1 leading-relaxed">{n.content}</p>
                                        <span className="text-[10px] text-text-muted shrink-0">
                                          {new Date(n.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                                        </span>
                                        <button onClick={() => deleteNoteMut.mutate(n.id)}
                                          className="text-text-muted hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100 shrink-0"
                                        >
                                          <X className="w-3 h-3" />
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {noteProjectId === project.id ? (
                                  <div className="flex gap-2">
                                    <input ref={noteRef} value={noteInput} onChange={(e) => setNoteInput(e.target.value)}
                                      onKeyDown={(e) => { if (e.key === "Enter" && noteInput.trim()) addNoteMut.mutate({ project_id: project.id, content: noteInput.trim() }) }}
                                      onBlur={() => setTimeout(() => setNoteProjectId(null), 200)}
                                      placeholder="Add note..."
                                      className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-lg px-2.5 py-1.5 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
                                    />
                                    <button onClick={() => { if (noteInput.trim()) addNoteMut.mutate({ project_id: project.id, content: noteInput.trim() }) }}
                                      disabled={!noteInput.trim() || addNoteMut.isPending}
                                      className="w-7 h-7 rounded-full bg-sky-500 text-white flex items-center justify-center shrink-0 disabled:opacity-40 transition-opacity"
                                    >
                                      {addNoteMut.isPending ? <Spinner size="sm" /> : <Plus className="w-3.5 h-3.5" />}
                                    </button>
                                  </div>
                                ) : (
                                  <button onClick={() => { setNoteProjectId(project.id); setNoteInput(""); setTimeout(() => noteRef.current?.focus(), 10) }}
                                    className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary transition-colors"
                                  >
                                    <Plus className="w-3 h-3" />
                                    Add note
                                  </button>
                                )}
                              </div>

                              {tasks.length === 0 && notes.length === 0 && (
                                <div className="text-center text-xs text-text-muted pt-1">No tasks or notes yet</div>
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

      {/* New Project Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="New Project">
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Name</label>
            <input ref={formRef} value={formName} onChange={(e) => setFormName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleCreate() }}
              placeholder="Project name"
              className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Priority</label>
            <div className="flex gap-1.5">
              {(["low", "medium", "high"] as const).map((p) => (
                <button key={p} onClick={() => setFormPriority(p)}
                  className={`flex-1 py-2 rounded-xl text-xs font-medium capitalize transition-all ${
                    formPriority === p
                      ? p === "high"
                        ? "bg-red-500/15 text-red-500 border border-red-500/30"
                        : p === "medium"
                          ? "bg-surface text-text-primary border border-border font-semibold"
                          : "bg-surface text-text-primary border border-border"
                      : "bg-surface text-text-muted border border-transparent hover:border-border"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Category</label>
              <input value={formCategory} onChange={(e) => setFormCategory(e.target.value)}
                placeholder="e.g. Web, Mobile..."
                className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
              />
            </div>
            <div>
              <button type="button" onClick={() => setFormHasDeadline(!formHasDeadline)}
                className="flex items-center gap-2 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors mb-1"
              >
                <div className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-all ${formHasDeadline ? "bg-emerald-500 border-transparent" : "border-text-muted"}`}>
                  {formHasDeadline && <span className="text-white text-[8px] font-bold">✓</span>}
                </div>
                Set deadline
              </button>
              {formHasDeadline && (
                <div className="relative mt-1">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
                  <input type="date" value={formDeadline} onChange={(e) => setFormDeadline(e.target.value)}
                    className="w-full bg-surface border border-border rounded-xl pl-9 pr-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary/30 transition-all [color-scheme:var(--color-scheme)]"
                  />
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Description (optional)</label>
            <textarea value={formDescription} onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Brief description..."
              rows={2}
              className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors resize-none"
            />
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={() => setShowModal(false)}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-surface text-text-secondary hover:text-text-primary border border-border transition-colors"
            >
              Cancel
            </button>
            <button onClick={handleCreate} disabled={!formName.trim() || createMut.isPending}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-blue-600 text-white disabled:opacity-40 transition-all"
            >
              {createMut.isPending ? <Spinner size="sm" /> : "Add Project"}
            </button>
          </div>
        </div>
      </Modal>
        </div>
      </div>
    </div>
  )
}
