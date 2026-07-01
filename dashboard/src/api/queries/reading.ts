import { api } from "../client"
import type { Book } from "../../types"

export async function fetchBooks(): Promise<Book[]> {
  const { data } = await api.get("/api/reading")
  return data.books ?? []
}

export async function addBook(book: { title: string; author?: string }): Promise<void> {
  await api.post("/api/reading", book)
}

export async function updateBook(id: number, updates: Partial<Book>): Promise<void> {
  await api.patch(`/api/reading/${id}`, updates)
}
