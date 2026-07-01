import { api } from "../client"
import type { Task } from "../../types"

export async function fetchTasks(status?: string, projectId?: number): Promise<Task[]> {
  const params: Record<string, string | number> = {}
  if (status) params.status = status
  if (projectId) params.project_id = projectId
  const { data } = await api.get("/api/tasks", { params })
  return data
}

export async function createTask(task: Partial<Task>): Promise<{ id: number }> {
  const { data } = await api.post("/api/tasks", task)
  return data
}

export async function completeTask(id: number): Promise<void> {
  await api.post(`/api/tasks/${id}/complete`)
}

export async function deleteTask(id: number): Promise<void> {
  await api.delete(`/api/tasks/${id}`)
}

export async function updateTask(id: number, updates: Partial<Task>): Promise<void> {
  await api.patch(`/api/tasks/${id}`, updates)
}

export async function moveTask(id: number, direction: "up" | "down"): Promise<void> {
  await api.post(`/api/tasks/${id}/move`, { direction })
}
