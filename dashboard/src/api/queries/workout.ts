import { api } from "../client"
import type { WorkoutResponse } from "../../types"

export async function fetchWorkoutStats(): Promise<WorkoutResponse> {
  const { data } = await api.get("/api/workout/stats")
  if (!data?.stats || !Array.isArray(data.recent)) throw new Error("Datele antrenamentelor sunt incomplete")
  return data
}

export async function logWorkout(session: {
  sport_name: string
  duration_min: number
  calories?: number
  notes?: string
}): Promise<void> {
  await api.post("/api/workout/log", session)
}
