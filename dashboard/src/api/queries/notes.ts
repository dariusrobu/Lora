import { api } from "../client"
import type { Note } from "../../types"

export async function fetchNotes(): Promise<Note[]> {
  const { data } = await api.get("/api/notes")
  return data
}

export async function createNote(note: { content: string; project_id?: number; type?: string; tags?: string[] }): Promise<{ id: number }> {
  const { data } = await api.post("/api/notes", note)
  return data
}

export async function deleteNote(id: number): Promise<void> {
  await api.delete(`/api/notes/${id}`)
}
