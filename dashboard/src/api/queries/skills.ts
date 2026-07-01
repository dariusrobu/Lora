import { api } from "../client"
import type { Skill } from "../../types"

export async function fetchSkills(): Promise<Skill[]> {
  const { data } = await api.get("/api/skills")
  return data
}

export async function logSkill(name: string): Promise<void> {
  await api.post("/api/skills", { name })
}
