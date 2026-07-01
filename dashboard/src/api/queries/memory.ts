import { api } from "../client"
import type { MemoryFact } from "../../types"

export async function fetchMemory(): Promise<MemoryFact[]> {
  const { data } = await api.get("/api/memory")
  return data
}

export async function saveMemory(fact: { fact: string; category?: string }): Promise<void> {
  await api.post("/api/memory", fact)
}

export async function deleteMemory(id: number): Promise<void> {
  await api.delete(`/api/memory/${id}`)
}
