import { api } from "../client"
import type { Project } from "../../types"

export async function fetchProjects(): Promise<Project[]> {
  const { data } = await api.get("/api/projects")
  return data
}

export async function fetchProjectDetail(id: number): Promise<Project> {
  const { data } = await api.get(`/api/projects/${id}`)
  return data
}

export async function createProject(data: { name: string; priority?: string; deadline?: string; category?: string; description?: string }): Promise<void> {
  await api.post("/api/projects", data)
}

export async function updateProject(id: number, updates: Partial<Project>): Promise<void> {
  await api.patch(`/api/projects/${id}`, updates)
}

export async function deleteProject(id: number): Promise<void> {
  await api.delete(`/api/projects/${id}`)
}