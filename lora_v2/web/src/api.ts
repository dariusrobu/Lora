export type Entry = { id: string; kind: "event" | "reminder" | "academic"; title: string; starts_at: string; ends_at?: string; notes?: string; status: string; version: number }
export type Task = { id: string; title: string; status: string; due_at?: string; project_id?: string; project_name?: string; version: number }
export type Project = { id: string; name: string; status: string; version: number }
export type Expense = { id: string; amount: number; currency: string; category: string; merchant?: string; description?: string; spent_at: string; version: number }
export type Income = { id: string; amount: number; currency: string; category?: string; source?: string; description?: string; received_at: string; version: number }
export type Meal = { id: string; eaten_at: string; description?: string; estimate_uncertain: boolean; version: number; calories?: number | null; protein_g?: number | null; carbs_g?: number | null; fat_g?: number | null }
export type MealItemDetail = { id: string; name: string; grams?: number | null; calories?: number | null; protein_g?: number | null; carbs_g?: number | null; fat_g?: number | null; nutrition_provider?: string | null; nutrition_source_title?: string | null; nutrition_source_url?: string | null }
export type MealDetail = Meal & { items: MealItemDetail[] }
export type Workout = { id: string; started_at: string; duration_minutes: number; activity: string; version: number }
export type Health = { id: string; log_date: string; sleep_hours?: number; sleep_quality?: string; water_ml?: number; weight_kg?: number; cigarettes?: number; notes?: string; version: number }
export type Today = { date: string; entries: Entry[]; tasks: Task[] }
export type Journal = { expenses: Expense[]; incomes: Income[]; meals: Meal[]; workouts: Workout[]; health: Health[] }
export type ActionResult = { status: string; message: string; entity_id?: string }
export type Proposal = { id: string; source: string; reason: string; command: { type: string; data: Record<string, unknown> }; expires_at: string }
export type AppleConflict = { id: string; entity_type: string; entity_id: string; local_title?: string }
export type AppleConflictDetail = { local: { title: string; at?: string; status: string; version: number } | null; apple: { title: string; at?: string; completed: boolean } | null; apple_deleted: boolean }
export type UniversityKind = "subject" | "schedule" | "attendance" | "grade" | "exam" | "vacation"
export type UniversityRecord = { id: string; version: number; [key: string]: unknown }
export type UniversityData = { subjects: UniversityRecord[]; schedules: UniversityRecord[]; attendance: UniversityRecord[]; grades: UniversityRecord[]; exams: UniversityRecord[]; vacations: UniversityRecord[]; semester: { semester_start: string; semester_end?: string; version: number } | null }

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
  decideFollowup: (id: string, choice: "done" | "tomorrow") => request<ActionResult>(`/proposals/${id}/followup`, { method: "POST", body: JSON.stringify({ choice }) }),
  appleConflicts: () => request<AppleConflict[]>("/apple/conflicts"),
  appleConflictDetail: (id: string) => request<AppleConflictDetail>(`/apple/conflicts/${id}`),
  resolveAppleConflict: (id: string, choice: "keep_local" | "use_apple") => request<{status: string; message: string}>(`/apple/conflicts/${id}/decision`, { method: "POST", body: JSON.stringify({ choice }) }),
  university: () => request<UniversityData>("/university"),
  universityWeek: (weekStart: string) => request<Entry[]>(`/university/week?week_start=${encodeURIComponent(weekStart)}`),
  academicCreate: (kind: UniversityKind, data: Record<string, unknown>) => request<{id: string; version: number}>(`/university/${kind}`, { method: "POST", body: JSON.stringify({ data }) }),
  academicEdit: (kind: UniversityKind, id: string, expected_version: number, data: Record<string, unknown>) => request<{id: string; version: number}>(`/university/${kind}/${id}`, { method: "PUT", body: JSON.stringify({ expected_version, data }) }),
  academicDelete: (kind: UniversityKind, id: string, expected_version: number) => request<{id: string; version: number}>(`/university/${kind}/${id}?expected_version=${expected_version}`, { method: "DELETE" }),
  academicSemester: (semester_start: string, semester_end: string | null, expected_version: number | null) => request<{version: number}>("/university/semester", { method: "PUT", body: JSON.stringify({ semester_start, semester_end, expected_version }) }),
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
  meal: (id: string) => request<MealDetail>(`/entities/meal/${id}`),
  edit: (kind: string, id: string, expected_version: number, data: Record<string, unknown>) => request<ActionResult>(`/entities/${kind}/${id}`, {
    method: "PUT", body: JSON.stringify({ expected_version, data }),
  }),
  remove: (kind: string, id: string, expected_version: number) => request<ActionResult>(`/entities/${kind}/${id}?expected_version=${expected_version}`, { method: "DELETE" }),
}
