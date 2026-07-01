import { api } from "../client"
import type { WorkoutResponse, WorkoutSession, WorkoutStats, PersonalRecord } from "../../types"

const sports = [
  { icon: "🏋️", name: "Gym", cat: "Forță" },
  { icon: "🏃", name: "Alergare", cat: "Cardio" },
  { icon: "🚴", name: "Ciclism", cat: "Cardio" },
  { icon: "🤸", name: "HIIT", cat: "Cardio" },
  { icon: "⚽", name: "Fotbal", cat: "Sport" },
  { icon: "🏀", name: "Baschet", cat: "Sport" },
  { icon: "🧘", name: "Yoga", cat: "Mobilitate" },
]

const exerciseNames = [
  "Bench Press", "Squat", "Deadlift", "Pull-ups", "Dips",
  "Overhead Press", "Barbell Row", "Bicep Curl", "Tricep Pushdown",
  "Leg Press", "Lateral Raise", "Face Pull", "Cable Fly",
]

function generateMock(): WorkoutResponse {
  const recent: WorkoutSession[] = []
  for (let i = 15; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    if (Math.random() > 0.35) {
      const sport = sports[Math.floor(Math.random() * sports.length)]
      const duration = 30 + Math.floor(Math.random() * 60)
      const exCount = 2 + Math.floor(Math.random() * 4)
      const exercises = Array.from({ length: exCount }, () => ({
        name: exerciseNames[Math.floor(Math.random() * exerciseNames.length)],
        sets: 3 + Math.floor(Math.random() * 2),
        reps: 8 + Math.floor(Math.random() * 7),
        weight_kg: Math.round((10 + Math.random() * 100) * 10) / 10,
      }))
      recent.push({
        id: 1000 + i,
        workout_date: d.toISOString().slice(0, 10),
        type: sport.name,
        icon: sport.icon,
        duration_min: duration,
        calories: Math.round(duration * 6.5),
        exercises: i % 2 === 0 ? exercises : undefined,
      })
    }
  }

  const totalSessions = recent.length
  const avgDuration = Math.round(recent.reduce((s, w) => s + w.duration_min, 0) / totalSessions)
  const typeCounts: Record<string, number> = {}
  recent.forEach((w) => { typeCounts[w.type] = (typeCounts[w.type] || 0) + 1 })
  const mostCommon = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null

  const prs = [
    { exercise_name: "Bench Press", max_weight: 85 },
    { exercise_name: "Squat", max_weight: 110 },
    { exercise_name: "Deadlift", max_weight: 140 },
    { exercise_name: "Overhead Press", max_weight: 50 },
    { exercise_name: "Pull-ups", max_weight: 20 },
  ]

  return {
    stats: { total_sessions: totalSessions, active_days: totalSessions, most_common_type: mostCommon, avg_duration: avgDuration },
    recent,
    personal_records: prs,
  }
}

const mock = generateMock()

export async function fetchWorkoutStats(): Promise<WorkoutResponse> {
  try {
    const { data } = await api.get("/api/workout/stats")
    if (data?.stats && data?.recent) return data
  } catch {}
  return mock
}

export async function logWorkout(session: {
  sport_name: string
  duration_min: number
  calories?: number
  notes?: string
}): Promise<void> {
  await api.post("/api/workout/log", session)
}
