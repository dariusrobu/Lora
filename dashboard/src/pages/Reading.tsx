import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { BookOpen, Plus, Star } from "lucide-react"
import { Card, Button, Input, Badge, Modal, Spinner } from "../components/ui"
import type { Book } from "../types"
import { fetchBooks, addBook, updateBook } from "../api/queries/reading"

const statusColors: Record<string, "default" | "secondary" | "success"> = {
  want_to_read: "default",
  reading: "secondary",
  done: "success",
}

export default function Reading() {
  const [modalOpen, setModalOpen] = useState(false)
  const [title, setTitle] = useState("")
  const [author, setAuthor] = useState("")
  const queryClient = useQueryClient()

  const { data: books, isLoading } = useQuery<Book[]>({
    queryKey: ["books"],
    queryFn: fetchBooks,
  })

  const addMutation = useMutation({
    mutationFn: addBook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["books"] })
      setModalOpen(false)
      setTitle("")
      setAuthor("")
    },
  })

  const updateMutation = useMutation({
    mutationFn: updateBook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["books"] }),
  })

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="h-6 w-6 text-indigo-500" />
          <h1 className="text-2xl font-bold">Reading</h1>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Add Book
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {books?.map((book) => (
          <motion.div
            key={book.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="p-4 h-full flex flex-col">
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <h3 className="font-semibold">{book.title}</h3>
                  {book.author && (
                    <p className="text-sm text-text-secondary">{book.author}</p>
                  )}
                </div>
                <Badge variant={statusColors[book.status] ?? "default"}>
                  {book.status.replace("_", " ")}
                </Badge>
              </div>

              {book.total_pages && (
                <div className="mt-auto">
                  <div className="flex justify-between text-sm text-text-secondary mb-1">
                    <span>
                      {book.pages_read ?? 0} / {book.total_pages}
                    </span>
                    <span>
                      {Math.round(((book.pages_read ?? 0) / book.total_pages) * 100)}%
                    </span>
                  </div>
                  <div className="h-1 bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all"
                      style={{
                        width: `${((book.pages_read ?? 0) / book.total_pages) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {book.rating && (
                <div className="flex items-center gap-1 mt-2">
                  <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                  <span className="text-sm">{book.rating}/5</span>
                </div>
              )}

              <div className="flex gap-2 mt-3">
                {book.status !== "done" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      updateMutation.mutate({
                        id: book.id,
                        pages_read: (book.pages_read ?? 0) + 1,
                      })
                    }
                  >
                    +1 Page
                  </Button>
                )}
                {book.status === "reading" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      updateMutation.mutate({
                        id: book.id,
                        status: "done",
                      })
                    }
                  >
                    Finish
                  </Button>
                )}
                {book.status === "want_to_read" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      updateMutation.mutate({
                        id: book.id,
                        status: "reading",
                      })
                    }
                  >
                    Start Reading
                  </Button>
                )}
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}>
        <div className="space-y-4 p-4">
          <h2 className="text-lg font-semibold">Add Book</h2>
          <Input
            autoFocus
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <Input
            placeholder="Author (optional)"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
          />
          <Button
            onClick={() => addMutation.mutate({ title, author })}
            disabled={!title.trim() || addMutation.isPending}
          >
            Add
          </Button>
        </div>
      </Modal>
    </div>
  )
}
