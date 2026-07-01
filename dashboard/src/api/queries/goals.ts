import { api } from "../client"
import type { Goal } from "../../types"

export async function fetchGoals(): Promise<Goal[]> {
  const { data } = await api.get("/api/goals")
  return data
}

export async function createGoal(goal: { title: string; time_horizon?: string; category?: string; description?: string }): Promise<void> {
  await api.post("/api/goals", goal)
}

export async function updateGoal(id: number, updates: Partial<Goal>): Promise<void> {
  await api.patch(`/api/goals/${id}`, updates)
}

export async function completeGoal(id: number): Promise<void> {
  await api.post(`/api/goals/${id}/complete`)
}

export async function deleteGoal(id: number): Promise<void> {
  await api.delete(`/api/goals/${id}`)
}

export async function addSubtask(goalId: number, title: string): Promise<void> {
  await api.post(`/api/goals/${goalId}/subtasks`, { title })
}

export async function toggleSubtask(subtaskId: number): Promise<void> {
  await api.post(`/api/goals/subtasks/${subtaskId}/toggle`)
}

export async function deleteSubtask(subtaskId: number): Promise<void> {
  await api.delete(`/api/goals/subtasks/${subtaskId}`)
}
