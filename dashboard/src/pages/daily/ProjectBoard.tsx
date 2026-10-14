import { useMemo, useState, type FormEvent } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, ChevronDown, FolderKanban, Plus, Search, X } from "lucide-react"
import { createProject, fetchProjects } from "../../api/queries/projects"
import { createTask, fetchTasks, updateTask } from "../../api/queries/tasks"
import type { Project, Task } from "../../types"
import { dateLabel } from "./date"
import { LoginRequired } from "./LoginRequired"
import { isUnauthorized } from "./isUnauthorized"

type Group = { key: string; title: string; projectId?: number; tasks: Task[]; project?: Project }

export default function ProjectBoard() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects })
  const tasks = useQuery({ queryKey: ["tasks", "pending"], queryFn: () => fetchTasks("pending") })
  const [search, setSearch] = useState("")
  const [showProjectForm, setShowProjectForm] = useState(false)
  const [projectName, setProjectName] = useState("")
  const [editingGroup, setEditingGroup] = useState<string | null>(null)
  const [taskTitle, setTaskTitle] = useState("")
  const [taskDate, setTaskDate] = useState("")
  const [taskProjectId, setTaskProjectId] = useState("")
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set())
  const activeEditingGroup = searchParams.get("action") === "task" ? "unassigned" : editingGroup

  const createProjectMutation = useMutation({ mutationFn: createProject, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["projects"] }); setProjectName(""); setShowProjectForm(false) } })
  const createTaskMutation = useMutation({ mutationFn: createTask, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["tasks"] }); queryClient.invalidateQueries({ queryKey: ["projects"] }); setTaskTitle(""); setTaskDate(""); setEditingGroup(null); setSearchParams({}, { replace: true }) } })
  const completeTaskMutation = useMutation({ mutationFn: (id: number) => updateTask(id, { status: "done" }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["tasks"] }); queryClient.invalidateQueries({ queryKey: ["projects"] }) } })

  const groups = useMemo<Group[]>(() => {
    const items = tasks.data ?? []
    const activeProjects = (projects.data ?? []).filter((project) => project.status !== "completed" && project.status !== "done")
    const result: Group[] = activeProjects.map((project) => ({ key: `project-${project.id}`, title: project.name, projectId: project.id, tasks: items.filter((task) => !task.university_subject_id && Number(task.project_id) === project.id), project }))
    const academic = items.filter((task) => !!task.university_subject_id)
    if (academic.length) result.push({ key: "university", title: "Facultate", tasks: academic })
    const unassigned = items.filter((task) => !task.university_subject_id && !task.project_id)
    result.push({ key: "unassigned", title: "Fără proiect", tasks: unassigned })
    return result.filter((group) => group.title.toLocaleLowerCase("ro-RO").includes(search.toLocaleLowerCase("ro-RO")) || group.tasks.some((task) => task.title.toLocaleLowerCase("ro-RO").includes(search.toLocaleLowerCase("ro-RO"))))
  }, [projects.data, tasks.data, search])

  const toggleGroup = (key: string) => setCollapsed((before) => { const next = new Set(before); if (next.has(key)) next.delete(key); else next.add(key); return next })
  const submitProject = (event: FormEvent) => { event.preventDefault(); if (projectName.trim()) createProjectMutation.mutate({ name: projectName.trim() }) }
  const submitTask = (event: FormEvent, group: Group) => {
    event.preventDefault()
    if (!taskTitle.trim()) return
    createTaskMutation.mutate({ title: taskTitle.trim(), project_id: group.projectId ?? (taskProjectId ? Number(taskProjectId) : null), due_date: taskDate || undefined, priority: "medium" })
  }
  if (isUnauthorized(projects.error, tasks.error, createProjectMutation.error, createTaskMutation.error, completeTaskMutation.error)) return <LoginRequired />

  return <div className="daily-page">
    <div className="daily-page-heading"><div><p className="daily-eyebrow">LUCRURI DE FĂCUT</p><h1>Proiecte și taskuri</h1><p className="daily-subtitle">Fiecare task la locul lui, cu următorul pas la vedere.</p></div><button type="button" className="daily-primary-button" onClick={() => setShowProjectForm((open) => !open)}><Plus size={17} /> Proiect</button></div>

    {showProjectForm && <form className="daily-panel daily-inline-form" onSubmit={submitProject}><div className="daily-section-heading"><h2>Proiect nou</h2><button type="button" onClick={() => setShowProjectForm(false)} aria-label="Închide"><X size={18} /></button></div><div className="daily-form-inline"><label className="daily-field"><span>Nume</span><input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Ex. Licență" autoFocus required /></label><button className="daily-primary-button" type="submit" disabled={createProjectMutation.isPending || !projectName.trim()}>Salvează</button></div>{createProjectMutation.isError && <p className="daily-inline-error">Proiectul nu a putut fi salvat.</p>}</form>}

    <label className="daily-search"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Caută proiecte și taskuri" aria-label="Caută proiecte și taskuri" /></label>
    {(projects.isPending || tasks.isPending) && <div className="daily-panel daily-state">Se încarcă proiectele și taskurile…</div>}
    {(projects.isError || tasks.isError) && <div className="daily-panel daily-state daily-error">Lista nu a putut fi încărcată. <button type="button" onClick={() => { projects.refetch(); tasks.refetch() }}>Reîncearcă</button></div>}
    {!projects.isPending && !tasks.isPending && !projects.isError && !tasks.isError && <div className="daily-project-list">
      {groups.length === 0 && <div className="daily-panel daily-state">Nu am găsit proiecte sau taskuri pentru „{search}”.</div>}
      {groups.map((group) => <section className="daily-panel daily-project-card" key={group.key}>
        <div className="daily-project-heading"><button type="button" onClick={() => toggleGroup(group.key)} aria-expanded={!collapsed.has(group.key) || activeEditingGroup === group.key}><span className="daily-project-icon"><FolderKanban size={18} /></span><span><strong>{group.title}</strong><small>{group.tasks.length} {group.tasks.length === 1 ? "task deschis" : "taskuri deschise"}</small></span><ChevronDown className={collapsed.has(group.key) && activeEditingGroup !== group.key ? "is-collapsed" : ""} size={18} /></button>{group.key === "university" ? <Link className="daily-project-add" to="/university" aria-label="Deschide Facultate pentru task nou"><Plus size={17} /></Link> : <button type="button" className="daily-project-add" onClick={() => { setEditingGroup(activeEditingGroup === group.key ? null : group.key); setSearchParams({}, { replace: true }); setTaskTitle(""); setTaskDate("") }} aria-label={`Adaugă task în ${group.title}`}><Plus size={17} /></button>}</div>
        {(!collapsed.has(group.key) || activeEditingGroup === group.key) && <div className="daily-project-body">
          {group.tasks.length === 0 ? <p className="daily-project-empty">Niciun task deschis.</p> : group.tasks.map((task) => <div className="daily-task-row" key={task.id}><button type="button" className="daily-check" onClick={() => completeTaskMutation.mutate(task.id)} disabled={completeTaskMutation.isPending} aria-label={`Marchează ${task.title} ca terminat`}><Check size={14} /></button><span className="daily-task-text"><strong>{task.title}</strong><small>{task.subject_name && `${task.subject_name} · `}{task.due_date ? `Până la ${dateLabel(task.due_date)}` : "Fără termen"}</small></span></div>)}
          {activeEditingGroup === group.key && <form className="daily-task-inline-form" onSubmit={(event) => submitTask(event, group)}><label className="daily-field"><span>Task nou</span><input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="Ce ai de făcut?" autoFocus required /></label>{group.key === "unassigned" && <label className="daily-field"><span>Proiect (opțional)</span><select value={taskProjectId} onChange={(event) => setTaskProjectId(event.target.value)}><option value="">Fără proiect</option>{(projects.data ?? []).filter((project) => project.status !== "completed" && project.status !== "done").map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label>}<label className="daily-field"><span>Termen (opțional)</span><input type="date" value={taskDate} onChange={(event) => setTaskDate(event.target.value)} /></label><div><button type="button" className="daily-text-button" onClick={() => { setEditingGroup(null); setSearchParams({}, { replace: true }) }}>Anulează</button><button type="submit" className="daily-primary-button" disabled={createTaskMutation.isPending || !taskTitle.trim()}>Salvează</button></div>{createTaskMutation.isError && <p className="daily-inline-error">Taskul nu a putut fi salvat.</p>}</form>}
        </div>}
      </section>)}
      {completeTaskMutation.isError && <p className="daily-inline-error">Taskul nu a putut fi actualizat.</p>}
    </div>}
  </div>
}
