import { api } from "../client"
import type { NewsArticle } from "../../types"

export async function fetchNews(category?: string, limit = 15): Promise<NewsArticle[]> {
  const params: Record<string, any> = { limit }
  if (category && category !== "toate") {
    params.category = category
  }
  const { data } = await api.get("/api/news", { params })
  return data
}
