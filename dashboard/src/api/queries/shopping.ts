import { api } from "../client"
import type { ShoppingItem } from "../../types"

export async function fetchShopping(): Promise<ShoppingItem[]> {
  const { data } = await api.get("/api/shopping")
  return data
}

export async function addShoppingItem(item: string, category?: string): Promise<void> {
  await api.post("/api/shopping", { item, category })
}

export async function toggleShoppingItem(id: number): Promise<void> {
  await api.patch(`/api/shopping/${id}`, { is_bought: true })
}

export async function deleteShoppingItem(id: number): Promise<void> {
  await api.delete(`/api/shopping/${id}`)
}
