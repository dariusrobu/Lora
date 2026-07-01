import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Circle, Loader2, ListTodo } from "lucide-react"
import { api } from "../../api/client"
import AnimatedNumber from "./AnimatedNumber"
import type { Task } from "../../types"

const mockTasks: Task[] = [
  { id: 1, title: "Review project proposal", priority: "high", status: "pending", created_at: new Date().toISOString() },
  { id: 2, title: "Buy groceries", priority: "medium", status: "pending", created_at: new Date().toISOString() },
  { id: 3, title: "Prepare presentation slides", priority: "medium", status: "pending", created_at: new Date().toISOString() },
]

async function fetchTasks(): Promise<Task[]> {
  try {
    const data = await api.get("/api/tasks")
    if (Array.isArray(data.data?.tasks)) return data.data.tasks
    return data.data ?? []
  } catch { return mockTasks }
}

export default function TasksWidget() {
  const qc = useQueryClient()
  const { data: tasks, isLoading } = useQuery({
    queryKey: ["kiosk-tasks"],
    queryFn: fetchTasks,
    refetchInterval: 60_000,
  })
  const complete = useMutation({
    mutationFn: (id: number) => api.patch(`/api/tasks/${id}`, { status: "done" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["kiosk-tasks"] }),
  })

  const pending = (tasks ?? []).filter((t: Task) => t.status === "pending")
  const count = pending.length

  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin text-orange-400 mx-auto mt-6" />

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-2">
        <ListTodo className="w-5 h-5 text-orange-400" />
        <span className="text-lg font-semibold tracking-[1.5px] text-orange-400 uppercase">Tasks</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-5xl font-light text-text-primary">
          <AnimatedNumber value={count} />
        </span>
        <span className="text-lg text-text-secondary">pending</span>
      </div>
      <div className="mt-3 space-y-2 flex-1 min-h-0 overflow-auto">
        {pending.length === 0 && (
          <p className="text-base text-text-muted">All clear ✨</p>
        )}
        {pending.slice(0, 3).map((t: Task) => (
          <button
            key={t.id}
            onClick={() => complete.mutate(t.id)}
            className="w-full flex items-center gap-2 text-left group"
          >
            {complete.isPending && complete.variables === t.id ? (
              <Loader2 className="w-4 h-4 animate-spin shrink-0 text-text-muted" />
            ) : (
              <Circle className="w-4 h-4 shrink-0 text-text-muted group-hover:text-orange-400 transition-colors" />
            )}
            <span className="text-lg text-text-secondary group-hover:text-text-primary truncate transition-colors">
              {t.title}
            </span>
            {t.priority === "high" && <span className="ml-auto text-sm text-red-400 shrink-0">●</span>}
          </button>
        ))}
        {pending.length > 3 && (
          <p className="text-base text-text-muted">+{pending.length - 3} more</p>
        )}
      </div>
    </div>
  )
}
