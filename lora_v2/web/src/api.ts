export type Entry = { id: string; kind: "event" | "reminder" | "academic"; title: string; starts_at: string; ends_at?: string; status: string; version: number }
export type Task = { id: string; title: string; status: string; due_at?: string; project_id?: string; project_name?: string; version: number }
export type Project = { id: string; name: string; status: string; version: number }
export type Expense = { id: string; amount: number; currency: string; category: string; merchant?: string; description?: string; spent_at: string; version: number }
export type Meal = { id: string; eaten_at: string; description?: string; estimate_uncertain: boolean; version: number }
export type Workout = { id: string; started_at: string; duration_minutes: number; activity: string; version: number }
export type Today = { date: string; entries: Entry[]; tasks: Task[] }
export type Journal = { expenses: Expense[]; meals: Meal[]; workouts: Workout[] }
export type ActionResult = { status: string; message: string; entity_id?: string }
export type Proposal = { id: string; reason: string; command: { type: string; data: Record<string, unknown> }; expires_at: string }

type TelegramWindow = Window & { Telegram?: { WebApp?: { initData?: string; ready?: () => void; expand?: () => void } } }
export const telegram = (window as TelegramWindow).Telegram?.WebApp

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!telegram?.initData) throw new Error("Deschide Lora din Telegram pentru a accesa datele.")
  const response = await fetch(`/api/v2${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Telegram-Init-Data": telegram.initData, ...options.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Cererea a eșuat (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  today: () => request<Today>("/today"),
  calendar: (from: string, to: string) => request<Entry[]>(`/calendar?from_at=${encodeURIComponent(from)}&to_at=${encodeURIComponent(to)}`),
  projects: () => request<Project[]>("/projects"),
  tasks: () => request<Task[]>("/tasks"),
  journal: () => request<Journal>("/journal"),
  proposals: () => request<Proposal[]>("/proposals"),
  decide: (id: string, accept: boolean) => request<ActionResult>(`/proposals/${id}/decision`, { method: "POST", body: JSON.stringify({ accept }) }),
  capture: (text: string) => request<{ id: string; status: string }>("/captures", { method: "POST", body: JSON.stringify({ external_id: crypto.randomUUID(), text }) }),
  photo: async (file: File, caption = "") => {
    if (!telegram?.initData) throw new Error("Deschide Lora din Telegram pentru a accesa datele.")
    const response = await fetch(`/api/v2/captures/photo?caption=${encodeURIComponent(caption)}`, {
      method: "POST", headers: { "X-Telegram-Init-Data": telegram.initData }, body: file,
    })
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "Nu am putut trimite fotografia.") }
    return response.json() as Promise<{ id: string; status: string }>
  },
  action: (type: string, data: Record<string, unknown>) => request<ActionResult>("/actions", {
    method: "POST",
    body: JSON.stringify({ idempotency_key: crypto.randomUUID(), command: { type, data } }),
  }),
  entity: (kind: string, id: string) => request<Record<string, unknown>>(`/entities/${kind}/${id}`),
  edit: (kind: string, id: string, expected_version: number, data: Record<string, unknown>) => request<ActionResult>(`/entities/${kind}/${id}`, {
    method: "PUT", body: JSON.stringify({ expected_version, data }),
  }),
  remove: (kind: string, id: string, expected_version: number) => request<ActionResult>(`/entities/${kind}/${id}?expected_version=${expected_version}`, { method: "DELETE" }),
}
