import { api } from "../client"
import type { FinanceSummary, Transaction } from "../../types"

export async function fetchFinanceSummary(): Promise<{
  summary: FinanceSummary
  categories: { category: string; total: number }[]
  budgets: FinanceBudget[]
}> {
  const { data } = await api.get("/api/finances/summary")
  return data
}

export interface FinanceBudget {
  category: string
  monthly_limit: number
  weekly_limit?: number | null
  monthly_spent: number
  weekly_spent: number
  current_spent?: number
}

function normalizeTransaction(row: Transaction & { tx_date?: string }): Transaction {
  return { ...row, transaction_date: row.transaction_date || row.tx_date || "" }
}

export async function fetchCategoryTransactions(category: string): Promise<Transaction[]> {
  const { data } = await api.get(`/api/finances/category/${encodeURIComponent(category)}`)
  if (Array.isArray(data)) return data.map(normalizeTransaction)
  if (Array.isArray(data?.transactions)) return data.transactions.map(normalizeTransaction)
  if (data?.detail) throw new Error(String(data.detail))
  return []
}

export async function updateFinanceBudget(payload: { category: string; amount: number; period: "weekly" | "monthly" }): Promise<void> {
  await api.put("/api/finances/budgets", payload)
}

export async function fetchFinanceHistory(limit = 20): Promise<Transaction[]> {
  const { data } = await api.get("/api/finances/history", { params: { limit } })
  return (Array.isArray(data) ? data : []).map(normalizeTransaction)
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
