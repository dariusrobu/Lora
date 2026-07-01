import { api } from "../client"
import type { NutritionResponse } from "../../types"

export async function fetchDailyNutrition(): Promise<NutritionResponse> {
  const { data } = await api.get("/api/nutrition/daily")
  return data
}

export async function logMeal(meal: {
  meal_type: string
  description: string
  calories: number
  protein?: number
  carbs?: number
  fat?: number
}): Promise<void> {
  await api.post("/api/nutrition", meal)
}
