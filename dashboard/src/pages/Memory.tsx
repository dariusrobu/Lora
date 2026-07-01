import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Brain, Plus, Trash2 } from "lucide-react"
import { Card, Button, Badge, Modal, Input, Spinner } from "../components/ui"
import type { MemoryFact } from "../types"
import { fetchMemory, saveMemory, deleteMemory } from "../api/queries/memory"

export default function Memory() {
  const [modalOpen, setModalOpen] = useState(false)
  const [fact, setFact] = useState("")
  const [category, setCategory] = useState("general")
  const queryClient = useQueryClient()

  const { data: facts, isLoading } = useQuery<MemoryFact[]>({
    queryKey: ["memory"],
    queryFn: fetchMemory,
  })

  const saveMutation = useMutation({
    mutationFn: saveMemory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory"] })
      setModalOpen(false)
      setFact("")
      setCategory("general")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteMemory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memory"] }),
  })

  const grouped = facts?.reduce<Record<string, MemoryFact[]>>((acc, f) => {
    const key = f.category || "uncategorized"
    ;(acc[key] ??= []).push(f)
    return acc
  }, {})

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-6 w-6 text-text-secondary" />
          <h1 className="text-2xl font-bold">Memory</h1>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Save Fact
        </Button>
      </div>

      {grouped &&
        Object.entries(grouped).map(([cat, items]) => (
          <div key={cat}>
            <h2 className="text-lg font-semibold capitalize mb-2">{cat}</h2>
            <div className="space-y-2">
              {items.map((item) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                >
                  <Card className="flex items-center justify-between p-3">
                    <div className="flex items-center gap-3">
                      <span>{item.fact}</span>
                      <Badge
                        variant={
                          item.confidence > 0.7
                            ? "highlight"
                            : item.confidence > 0.4
                              ? "default"
                              : "muted"
                        }
                      >
                        {Math.round(item.confidence * 100)}%
                      </Badge>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteMutation.mutate(item.id)}
                    >
                      <Trash2 className="h-4 w-4 text-text-secondary" />
                    </Button>
                  </Card>
                </motion.div>
              ))}
            </div>
          </div>
        ))}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}>
        <div className="space-y-4 p-4">
          <h2 className="text-lg font-semibold">Save Memory Fact</h2>
          <textarea
            autoFocus
            className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/30 min-h-[80px]"
            placeholder="What do you want to remember?"
            value={fact}
            onChange={(e) => setFact(e.target.value)}
          />
          <Input
            placeholder="Category (e.g. personal, work, trivia)"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
          <Button
            onClick={() => saveMutation.mutate({ fact, category })}
            disabled={!fact.trim() || saveMutation.isPending}
          >
            Save
          </Button>
        </div>
      </Modal>
    </div>
  )
}
