import { api } from "./client"

export async function login(email: string, password: string): Promise<string> {
  const { data } = await api.post("/api/auth/login", { email, password })
  return data.access_token
}

export function logout() {
  localStorage.removeItem("lora_token")
}

export async function fetchHealth() {
  const { data } = await api.get("/api/health")
  return data
}

export async function fetchProfile() {
  try {
    const { data } = await api.get("/api/profile")
    if (data?.name) return data
  } catch {}
  return { id: 1, name: "Robu", tone: "friendly", timezone: "Europe/Bucharest" }
}
