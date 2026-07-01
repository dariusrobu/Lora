import { api } from "../client"
import type { HealthResponse } from "../../types"

export async function fetchHealthSummary(): Promise<HealthResponse> {
  const { data } = await api.get("/api/health/summary")
  return data
}

export async function logHealth(entry: {
  sleep_hours?: number
  water_ml?: number
  weight_kg?: number
  cigarettes?: number
}): Promise<void> {
  await api.post("/api/health", entry)
}
