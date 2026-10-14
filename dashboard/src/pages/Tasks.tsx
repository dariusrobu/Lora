import { useState, useMemo, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { fetchTasks, createTask, completeTask, deleteTask, updateTask } from "../api/queries/tasks"
import { fetchProjects } from "../api/queries/projects"
import { api } from "../api/client"
import { Card, Spinner, PageHeader, DateField } from "../components/ui"
import { Circle, CheckCircle2, Trash2, Plus, ChevronDown, Search, Calendar } from "lucide-react"
import type { Task } from "../types"
import "./Tasks.css"

const today = () => {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

function getDueDateInfo(dueDate: string | undefined, status: string) {
  if (status === "done") return { label: "Done", color: "text-emerald-500" }
  if (!dueDate) return { label: null, color: null }
  const t = today()
  const d = new Date(dueDate + "T00:00:00")
  const diff = (d.getTime() - t.getTime()) / (1000 * 60 * 60 * 24)
  if (diff < 0) return { label: dueDate, color: "text-red-500" }
  if (diff === 0) return { label: "Today", color: "text-yellow-500" }
  if (diff === 1) return { label: "Tomorrow", color: "text-orange-500" }
  return { label: dueDate, color: "text-text-muted" }
}

const priorityIcon = (p: string) => {
  switch (p) {
    case "high": return "❗"
    case "medium": return "‼️"
    case "low": return "❗"
    default: return ""
  }
}

const priorityOpacity = (p: string) => {
  switch (p) {
    case "high": return "opacity-100"
    case "medium": return "opacity-60"
    case "low": return "opacity-30"
    default: return "opacity-20"
  }
}

interface Section {
  label: string
  tasks: Task[]
  color?: string
}

function groupTasks(tasks: Task[], groupBy: string): Section[] {
  const t = today()
  const tomorrow = new Date(t)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const endOfWeek = new Date(t)
  endOfWeek.setDate(endOfWeek.getDate() + (6 - t.getDay()))

  switch (groupBy) {
    case "due_date": {
      const sections: Section[] = []
      if (tasks.some((x) => x.due_date && new Date(x.due_date + "T00:00:00") < t && x.status !== "done")) {
        sections.push({ label: "Overdue", color: "text-red-500", tasks: tasks.filter((x) => x.due_date && new Date(x.due_date + "T00:00:00") < t && x.status !== "done") })
      }
      if (tasks.some((x) => x.due_date && new Date(x.due_date + "T00:00:00").getTime() === t.getTime())) {
        sections.push({ label: "Today", color: "text-yellow-500", tasks: tasks.filter((x) => x.due_date && new Date(x.due_date + "T00:00:00").getTime() === t.getTime()) })
      }
      if (tasks.some((x) => x.due_date && new Date(x.due_date + "T00:00:00").getTime() === tomorrow.getTime())) {
        sections.push({ label: "Tomorrow", color: "text-orange-500", tasks: tasks.filter((x) => x.due_date && new Date(x.due_date + "T00:00:00").getTime() === tomorrow.getTime()) })
      }
      if (tasks.some((x) => x.due_date && new Date(x.due_date + "T00:00:00") > tomorrow && new Date(x.due_date + "T00:00:00") <= endOfWeek && x.status !== "done")) {
        sections.push({ label: "This week", tasks: tasks.filter((x) => x.due_date && new Date(x.due_date + "T00:00:00") > tomorrow && new Date(x.due_date + "T00:00:00") <= endOfWeek && x.status !== "done") })
      }
      if (tasks.some((x) => x.due_date && new Date(x.due_date + "T00:00:00") > endOfWeek && x.status !== "done")) {
        sections.push({ label: "Later", tasks: tasks.filter((x) => x.due_date && new Date(x.due_date + "T00:00:00") > endOfWeek && x.status !== "done") })
      }
      if (tasks.some((x) => !x.due_date && x.status !== "done")) {
        sections.push({ label: "No date", tasks: tasks.filter((x) => !x.due_date && x.status !== "done") })
      }
      if (tasks.some((x) => x.status === "done")) {
        sections.push({ label: "Done", color: "text-emerald-500", tasks: tasks.filter((x) => x.status === "done") })
      }
      return sections
    }
    case "priority":
      return (["high", "medium", "low"] as const).map((p) => ({
        label: p.charAt(0).toUpperCase() + p.slice(1),
        tasks: tasks.filter((x) => x.priority === p),
      })).filter((s) => s.tasks.length > 0)
    case "project": {
      const map = new Map<string, Task[]>()
      tasks.forEach((x) => {
        const key = x.university_subject_id ? "University" : (x.project_name ?? "No project")
        if (!map.has(key)) map.set(key, [])
        map.get(key)!.push(x)
      })
      return Array.from(map.entries()).map(([label, tasks]) => ({ label, tasks }))
    }
    case "category": {
      const map = new Map<string, Task[]>()
      tasks.forEach((x) => {
        const key = x.tags?.[0] || "Fără categorie"
        if (!map.has(key)) map.set(key, [])
        map.get(key)!.push(x)
      })
      return Array.from(map.entries()).map(([label, tasks]) => ({ label, tasks }))
    }
    default:
      return [{ label: "", tasks }]
  }
}

function isDoneThisWeek(task: Task): boolean {
  if (task.status !== "done" || !task.completed_at) return false
  const completed = new Date(task.completed_at)
  const today = new Date()
  const monday = new Date(today)
  const day = monday.getDay() || 7
  monday.setDate(monday.getDate() - day + 1)
  monday.setHours(0, 0, 0, 0)
  return completed >= monday
}

export default function Tasks() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [filter, setFilter] = useState<"all" | "pending" | "done">("all")
  const [groupBy, setGroupBy] = useState<string>("due_date")
  const [projectFilter, setProjectFilter] = useState("all")
  const [search, setSearch] = useState("")
  const [searchOpen, setSearchOpen] = useState(false)
  const [showGroupMenu, setShowGroupMenu] = useState(false)
  const [showMore, setShowMore] = useState(false)
  const [showDone, setShowDone] = useState(false)

  const [showModal, setShowModal] = useState(() => searchParams.get("action") === "add")
  const [formTitle, setFormTitle] = useState("")
  const [formPriority, setFormPriority] = useState<"low" | "medium" | "high">("medium")
  const [formCategory, setFormCategory] = useState("")
  const [formProjectId, setFormProjectId] = useState("")
  const [formUniversitySubjectId, setFormUniversitySubjectId] = useState("")
  const [formUniversityType, setFormUniversityType] = useState("curs")
  const [formHasDue, setFormHasDue] = useState(false)
  const [formDue, setFormDue] = useState("")
  const formRef = useRef<HTMLInputElement>(null)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editValue, setEditValue] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [editDueDate, setEditDueDate] = useState("")
  const [editPriority, setEditPriority] = useState<"low" | "medium" | "high">("medium")
  const [editCategory, setEditCategory] = useState("")
  const [editProjectId, setEditProjectId] = useState("")
  const editRef = useRef<HTMLInputElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus()
  }, [searchOpen])

  const qc = useQueryClient()

  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => fetchTasks("all"),
  })
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: fetchProjects })
  const { data: universityData } = useQuery({
    queryKey: ["university"],
    queryFn: async () => (await api.get("/api/university/summary")).data,
  })
  const universitySubjects = universityData?.subjects ?? []

  const completeMut = useMutation({
    mutationFn: completeTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  })

  const createMut = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      setShowModal(false)
      setFormTitle("")
      setFormDue("")
      setFormPriority("medium")
      setFormCategory("")
      setFormProjectId("")
    },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: Partial<Task> }) => updateTask(id, updates),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  })

  const filtered = useMemo(() => {
    // Keep historical completed tasks stored for reporting, but only show
    // completions from the current week in the task list.
    let result = (tasks ?? []).filter((task) => task.status !== "done" || isDoneThisWeek(task))
    if (filter === "pending") result = result.filter((t) => t.status !== "done")
    else if (filter === "done") result = result.filter((t) => t.status === "done")
    if (projectFilter === "university") result = result.filter((t) => Boolean(t.university_subject_id))
    else if (projectFilter !== "all") result = result.filter((t) => String(t.project_id ?? "") === projectFilter)
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter((t) => t.title.toLowerCase().includes(q))
    }
    return result
  }, [tasks, filter, projectFilter, search])

  const completedCount = (tasks ?? []).filter((t) => t.status === "done").length
  const totalCount = tasks?.length ?? 0
  const pct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  const sections = useMemo(() => groupTasks(filtered, groupBy), [filtered, groupBy])

  const filters = ["all", "pending", "done"] as const
  const groupOptions = [
    { key: "due_date", label: "Due Date" },
    { key: "priority", label: "Priority" },
    { key: "project", label: "Project" },
    { key: "category", label: "Category" },
    { key: "none", label: "None" },
  ] as const

  const openModal = () => {
    setFormTitle("")
    setFormPriority("medium")
    setFormCategory("")
    setFormProjectId("")
    setFormUniversitySubjectId("")
    setFormUniversityType("curs")
    setFormHasDue(false)
    setFormDue("")
    setShowModal(true)
    setTimeout(() => formRef.current?.focus(), 100)
  }

  useEffect(() => {
    if (searchParams.get("action") === "add") setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  const handleCreate = () => {
    if (!formTitle.trim() || createMut.isPending || (formProjectId === "university" && !formUniversitySubjectId)) return
    const payload: Partial<Task> = { title: formTitle.trim(), priority: formPriority }
    if (formCategory.trim()) payload.tags = [formCategory.trim()]
    if (formProjectId) payload.project_id = Number(formProjectId)
    if (formProjectId === "university" && formUniversitySubjectId) {
      payload.university_subject_id = Number(formUniversitySubjectId)
      payload.class_type = formUniversityType
      delete payload.project_id
    }
    if (formHasDue && formDue) payload.due_date = formDue
    createMut.mutate(payload)
  }

  const startEdit = (task: Task) => {
    setEditingId(task.id)
    setEditValue(task.title)
    setEditDescription(task.description || task.notes || "")
    setEditDueDate(task.due_date || "")
    setEditPriority(task.priority)
    setEditCategory(task.tags?.[0] || "")
    setEditProjectId(task.project_id ? String(task.project_id) : "")
    setTimeout(() => editRef.current?.focus(), 10)
  }

  const saveEdit = (taskId: number) => {
    if (editValue.trim()) updateMut.mutate({ id: taskId, updates: { title: editValue.trim(), description: editDescription, due_date: editDueDate || undefined, priority: editPriority, tags: editCategory.trim() ? [editCategory.trim()] : [], project_id: editProjectId ? Number(editProjectId) : null } })
    setEditingId(null)
  }

  const cyclePriority = (task: Task) => {
    const next = task.priority === "high" ? "medium" : task.priority === "medium" ? "low" : "high"
    updateMut.mutate({ id: task.id, updates: { priority: next } })
  }

  if (isLoading) return <Spinner className="py-12" />

  return (
    <div className="card-liquid-page tasks-page">
      <div className="card-liquid-page-content p-6">
        <div className="flex flex-col">
          <PageHeader title="Tasks" action={<button onClick={openModal} className="inline-flex items-center gap-1.5 rounded-xl border border-primary/25 bg-primary/10 px-3 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/15"><Plus className="h-3.5 w-3.5" />Adaugă</button>} />

      {/* Progress bar */}
      {totalCount > 0 && (
        <div className="mb-5">
          <div className="flex justify-between text-xs text-text-secondary mb-1.5">
            <span>{completedCount}/{totalCount} done</span>
            <span>{pct}%</span>
          </div>
          <div className="h-1 bg-surface rounded-full overflow-hidden">
            <div className="h-full bg-violet-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {/* Segmented control + group dropdown */}
      <div className="tasks-toolbar mb-4 flex flex-wrap items-center gap-2">
        <div className="flex p-0.5 rounded-full bg-surface border border-border">
          {filters.map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                filter === f ? "bg-white/10 dark:bg-white/[0.08] font-semibold text-text-primary" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {f === "all" ? "All" : f === "pending" ? "Pending" : "Done"}
            </button>
          ))}
        </div>
        <select aria-label="Filtrează după proiect" data-active={projectFilter !== "all"} value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)} className="min-w-0 max-w-full rounded-xl border border-border bg-surface text-xs font-medium text-text-secondary sm:max-w-56">
          <option value="all">Toate proiectele</option>
          <option value="university">University</option>
          {(projects ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <div className="relative">
          <button onClick={() => setShowGroupMenu(!showGroupMenu)}
            aria-expanded={showGroupMenu}
            aria-label="Grupează taskurile"
            className="flex min-h-11 items-center gap-2 rounded-xl border border-border bg-surface px-3 text-xs font-medium text-text-secondary transition-colors hover:border-primary/30 hover:text-primary"
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
                    className={`min-h-11 w-full text-left px-3 py-2 text-xs transition-colors ${
                      groupBy === g.key ? "bg-primary/10 text-primary font-medium" : "text-text-secondary hover:text-text-primary hover:bg-surface"
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
        <div className={`ml-auto flex items-center rounded-full border transition-all duration-200 ${searchOpen ? "w-48 border-border bg-surface" : "w-8 border-transparent"}`}>
          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="w-8 h-8 shrink-0 flex items-center justify-center rounded-full text-text-muted hover:text-text-primary hover:bg-surface transition-colors"
            aria-label="Caută taskuri"
          >
            <Search className="w-3.5 h-3.5" />
          </button>
          <input
            ref={searchRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") { setSearchOpen(false); setSearch("") } }}
            placeholder="Caută taskuri..."
            tabIndex={searchOpen ? 0 : -1}
            className={`min-w-0 flex-1 bg-transparent pr-2 text-xs text-text-primary placeholder:text-text-muted outline-none transition-opacity ${searchOpen ? "opacity-100" : "opacity-0 pointer-events-none"}`}
          />
          {searchOpen && search && (
            <button type="button" onClick={() => setSearch("")} className="mr-2 text-text-muted hover:text-text-primary" aria-label="Șterge căutarea">×</button>
          )}
        </div>
      </div>

      <div className="order-2">
      {/* Task list */}
      {sections.length === 0 ? (
        <Card><p className="text-sm text-text-muted text-center py-8">No tasks found</p></Card>
      ) : (
        <div className="space-y-5">
          {sections.map((section) => {
            const isDoneSection = section.label === "Done"
            const visibleTasks = isDoneSection
              ? (showDone ? section.tasks : [])
              : (showMore ? section.tasks : section.tasks.slice(0, 5))
            if (isDoneSection && !showDone) {
              return (
                <button key={section.label} onClick={() => setShowDone(true)} className="flex w-full items-center gap-2 px-1 py-2 text-left text-xs text-text-muted hover:text-text-primary transition-colors">
                  <span className="font-semibold uppercase tracking-wider">Finalizate</span>
                  <span>· {section.tasks.length}</span>
                  <ChevronDown className="ml-auto w-3.5 h-3.5" />
                </button>
              )
            }
            return (
            <div key={section.label}>
              {section.label && (
                <div className="flex items-center gap-2 mb-2 px-1">
                  <span className={`text-xs font-semibold uppercase tracking-wider ${section.color ?? "text-text-muted"}`}>
                    {section.label}
                  </span>
                  <span className="text-xs text-text-muted">· {section.tasks.length}</span>
                  <div className="flex-1 h-px bg-border" />
                </div>
              )}
              <div className="space-y-0.5">
                <AnimatePresence>
                  {visibleTasks.slice().sort((a, b) => {
                    const order = { high: 0, medium: 1, low: 2 }
                    return (order[a.priority] ?? 3) - (order[b.priority] ?? 3)
                  }).map((task) => {
                    const dueInfo = getDueDateInfo(task.due_date, task.status)
                    return (
                      <motion.div key={task.id} layout initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}>
                        <div className="flex items-center gap-2.5 py-2 px-3 rounded-xl hover:bg-surface transition-colors group">
                          <button onClick={() => {
                            if (task.status === "done") updateMut.mutate({ id: task.id, updates: { status: "pending" } })
                            else completeMut.mutate(task.id)
                          }}>
                            {task.status === "done" ? (
                              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                            ) : (
                              <Circle className="w-5 h-5 text-text-muted hover:text-text-secondary transition-colors" />
                            )}
                          </button>

                          <div className="flex-1 min-w-0">
                            {editingId === task.id ? (
                              <div className="space-y-1.5 rounded-xl border border-border bg-surface p-2" onClick={(e) => e.stopPropagation()}><input ref={editRef} value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") saveEdit(task.id)
                                  if (e.key === "Escape") setEditingId(null)
                                }}
                                className="w-full bg-surface border border-border rounded-lg px-2 py-0.5 text-sm text-text-primary outline-none"
                                onClick={(e) => e.stopPropagation()}
                              />
                                <input value={editDescription} onChange={(e) => setEditDescription(e.target.value)} placeholder="Descriere" className="w-full rounded-lg border border-border bg-transparent px-2 py-1 text-xs text-text-secondary outline-none" />
                                <div className="flex flex-wrap gap-1.5"><select value={editProjectId} onChange={(e) => setEditProjectId(e.target.value)} className="h-8 min-w-32 flex-1 rounded-lg border border-border bg-transparent px-2 py-1 text-xs"><option value="">Fără proiect</option>{(projects ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select><input value={editCategory} onChange={(e) => setEditCategory(e.target.value)} placeholder="Categorie" className="h-8 min-w-28 flex-1 rounded-lg border border-border bg-transparent px-2 py-1 text-xs" /><DateField value={editDueDate} onChange={(e) => setEditDueDate(e.target.value)} aria-label="Data limită" className="h-8 rounded-lg px-2 py-1 text-xs" /><select value={editPriority} onChange={(e) => setEditPriority(e.target.value as "low" | "medium" | "high")} className="rounded-lg border border-border bg-transparent px-2 py-1 text-xs"><option value="low">Prioritate mică</option><option value="medium">Prioritate medie</option><option value="high">Prioritate mare</option></select><button type="button" onClick={() => saveEdit(task.id)} className="rounded-lg bg-primary px-2 py-1 text-xs text-white">Salvează</button><button type="button" onClick={() => setEditingId(null)} className="rounded-lg border border-border px-2 py-1 text-xs">Anulează</button></div></div>
                            ) : (
                              <button onClick={() => startEdit(task)}
                                className={`text-sm text-left w-full truncate transition-all ${task.status === "done" ? "line-through text-text-muted" : "text-text-primary"}`}
                              >
                                {task.title}
                              </button>
                            )}
                          </div>

                          {dueInfo.label && (
                            <span className={`text-xs shrink-0 ${dueInfo.color}`}>{dueInfo.label}</span>
                          )}

                          <button onClick={() => cyclePriority(task)}
                            className={`text-xs shrink-0 leading-none transition-all hover:opacity-100 ${priorityOpacity(task.priority)}`} title={task.priority}
                          >
                            {priorityIcon(task.priority)}
                          </button>

                          <button onClick={() => deleteMut.mutate(task.id)}
                            className="text-text-muted hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </motion.div>
                    )
                  })}
                </AnimatePresence>
              </div>
              {!isDoneSection && section.tasks.length > 5 && !showMore && (
                <button onClick={() => setShowMore(true)} className="mt-2 px-1 text-xs text-text-secondary hover:text-text-primary transition-colors">
                  Arată încă {section.tasks.length - 5} {section.tasks.length - 5 === 1 ? "task" : "taskuri"}
                </button>
              )}
              {isDoneSection && showDone && (
                <button onClick={() => setShowDone(false)} className="mt-2 px-1 text-xs text-text-secondary hover:text-text-primary transition-colors">
                  Ascunde finalizatele
                </button>
              )}
            </div>
            )
          })}
          {showMore && filtered.some((task) => task.status !== "done") && (
            <button onClick={() => setShowMore(false)} className="px-1 text-xs text-text-secondary hover:text-text-primary transition-colors">
              Arată mai puține
            </button>
          )}
        </div>
      )}
      </div>

      {/* Inline new task form */}
      <AnimatePresence initial={false}>
        {showModal && <motion.div initial={{ opacity: 0, height: 0, y: -8 }} animate={{ opacity: 1, height: "auto", y: 0 }} exit={{ opacity: 0, height: 0, y: -8 }} className="order-1 mb-6 overflow-hidden rounded-2xl border border-border bg-surface/70 p-4 sm:p-5">
        <div className="flex items-center justify-between mb-4"><h2 className="text-base font-semibold text-text-primary">New Task</h2><button type="button" onClick={() => setShowModal(false)} className="text-xs text-text-muted hover:text-text-primary">Cancel</button></div>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Title</label>
            <input ref={formRef} value={formTitle} onChange={(e) => setFormTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleCreate() }}
              placeholder="What needs to be done?"
              className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Project</label>
            <select value={formProjectId} onChange={(e) => setFormProjectId(e.target.value)} className="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary/30">
              <option value="">Fără proiect</option>
              <option value="university">University</option>
              {(projects ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            {formProjectId === "university" && <div className="mt-2 grid gap-2 sm:grid-cols-2"><select value={formUniversitySubjectId} onChange={(e) => setFormUniversitySubjectId(e.target.value)} className="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-text-primary outline-none"><option value="">Alege materia</option>{universitySubjects.map((subject: any) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select><select value={formUniversityType} onChange={(e) => setFormUniversityType(e.target.value)} className="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-text-primary outline-none"><option value="curs">Curs</option><option value="seminar">Seminar</option></select></div>}
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Category</label>
            <input value={formCategory} onChange={(e) => setFormCategory(e.target.value)} placeholder="ex. Facultate, Personal, Casă" className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors" />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Priority</label>
            <div className="flex gap-1.5">
              {(["low", "medium", "high"] as const).map((p) => (
                <button key={p} onClick={() => setFormPriority(p)}
                  aria-pressed={formPriority === p}
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

          <div>
            <button type="button" onClick={() => setFormHasDue(!formHasDue)}
              className="flex items-center gap-2 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors mb-1"
            >
              <div className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-all ${formHasDue ? "bg-emerald-500 border-transparent" : "border-text-muted"}`}>
                {formHasDue && <span className="text-white text-[8px] font-bold">✓</span>}
              </div>
              Set due date
            </button>
            {formHasDue && (
              <div className="relative mt-1">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
                <DateField value={formDue} onChange={(e) => setFormDue(e.target.value)} aria-label="Data limită" className="pl-9" />
              </div>
            )}
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={() => setShowModal(false)}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-surface text-text-secondary hover:text-text-primary border border-border transition-colors"
            >
              Cancel
            </button>
            <button onClick={handleCreate} disabled={!formTitle.trim() || createMut.isPending || (formProjectId === "university" && !formUniversitySubjectId)}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-primary text-white shadow-sm hover:bg-primary-hover disabled:pointer-events-none disabled:opacity-40 transition-all"
            >
              {createMut.isPending ? <Spinner size="sm" /> : "Add Task"}
            </button>
          </div>
        </div></motion.div>}
      </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
