import { api } from "../client"
import type { FinanceSummary, Transaction } from "../../types"

export async function fetchFinanceSummary(): Promise<{
  summary: FinanceSummary
  categories: { category: string; total: number }[]
}> {
  const { data } = await api.get("/api/finances/summary")
  return data
}

export async function fetchFinanceHistory(limit = 20): Promise<Transaction[]> {
  const { data } = await api.get("/api/finances/history", { params: { limit } })
  return data
}

export async function createTransaction(tx: {
  amount: number
  category: string
  description?: string
  type: string
}): Promise<void> {
  await api.post("/api/finances", tx)
}

export async function deleteTransaction(id: number): Promise<void> {
  await api.delete(`/api/finances/${id}`)
}
