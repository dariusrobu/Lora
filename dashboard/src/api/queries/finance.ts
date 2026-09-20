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

export async function fetchProductMemories() {
  const { data } = await api.get("/api/finances/product-memories")
  return data
}

export async function deleteProductMemory(id: number): Promise<void> {
  await api.delete(`/api/finances/product-memories/${id}`)
}

export async function fetchMerchantMemories() {
  const { data } = await api.get("/api/finances/merchant-memories")
  return data
}

export async function deleteMerchantMemory(id: number): Promise<void> {
  await api.delete(`/api/finances/merchant-memories/${id}`)
}

