import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { StickyNote, Pin, Trash2, Plus } from "lucide-react"
import { Card, Button, Badge, Modal, Spinner } from "../components/ui"
import type { Note } from "../types"
import { fetchNotes, createNote, deleteNote } from "../api/queries/notes"

export default function Notes() {
  const [modalOpen, setModalOpen] = useState(false)
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const queryClient = useQueryClient()

  const { data: notes, isLoading } = useQuery<Note[]>({
    queryKey: ["notes"],
    queryFn: fetchNotes,
  })

  const createMutation = useMutation({
    mutationFn: createNote,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes"] })
      setModalOpen(false)
      setTitle("")
      setBody("")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteNote,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notes"] }),
  })

  const handleCreate = () => {
    if (!title.trim()) return
    createMutation.mutate({ title: title.trim(), body: body.trim() })
  }

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StickyNote className="h-6 w-6 text-blue-500" />
          <h1 className="text-2xl font-bold">Notes</h1>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> New Note
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {notes?.map((note) => (
          <motion.div
            key={note.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="relative p-4 h-full">
              {note.is_pinned && (
                <Pin className="absolute top-2 right-2 h-4 w-4 text-yellow-500 fill-yellow-500" />
              )}
              <h3 className="font-semibold mb-1 pr-6">{note.title}</h3>
              <p className="text-sm text-text-secondary mb-3 line-clamp-3">
                {note.body}
              </p>
              <div className="flex items-center justify-between">
                <div className="flex gap-1 flex-wrap">
                  {note.tags?.map((tag) => (
                    <Badge key={tag}>{tag}</Badge>
                  ))}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => deleteMutation.mutate(note.id)}
                >
                  <Trash2 className="h-4 w-4 text-red-400" />
                </Button>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}>
        <div className="space-y-4 p-4">
          <h2 className="text-lg font-semibold">New Note</h2>
          <input
            autoFocus
            className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/30"
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <textarea
            className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/30 min-h-[120px]"
            placeholder="Body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <Button onClick={handleCreate} disabled={createMutation.isPending}>
            Save
          </Button>
        </div>
      </Modal>
    </div>
  )
}
