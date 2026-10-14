import { api } from "../client"
import type { CalendarDay } from "../../types"

function fmt(d: Date): string {
  // Use local calendar date; UTC conversion shifts midnight back one day in
  // Romania and made Monday requests load the previous week.
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

export async function fetchWeek(refDate?: Date): Promise<CalendarDay[]> {
  const params = refDate ? { ref_date: fmt(refDate) } : {}
  const { data } = await api.get("/api/calendar/week", { params })
  return data.days ?? []
}

export async function createEvent(data: { title: string; date: string; time?: string; description?: string; type?: string }): Promise<{ id: number }> {
  const res = await api.post("/api/calendar/events", data)
  return res.data
}

export async function deleteEvent(id: number): Promise<void> {
  await api.delete(`/api/calendar/events/${id}`)
}
