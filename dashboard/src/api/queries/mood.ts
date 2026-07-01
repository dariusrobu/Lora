import { api } from "../client"
import type { MoodEntry } from "../../types"

export async function fetchMoodWeekly(): Promise<MoodEntry[]> {
  const { data } = await api.get("/api/mood/weekly")
  return data
}

export async function fetchMoodMonthly(): Promise<MoodEntry[]> {
  const { data } = await api.get("/api/mood/monthly")
  return data
}

export async function logMood(data: { mood: string; date?: string }): Promise<void> {
  await api.post("/api/mood", data)
}

export async function deleteMood(date: string): Promise<void> {
  await api.delete(`/api/mood/${date}`)
}
