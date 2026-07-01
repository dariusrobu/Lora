import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { fetchShopping, addShoppingItem, toggleShoppingItem, deleteShoppingItem } from "../api/queries/shopping"
import { Card } from "../components/ui/Card"
import { Button } from "../components/ui/Button"
import { Badge } from "../components/ui/Badge"
import { Input } from "../components/ui/Input"
import { Spinner } from "../components/ui/Spinner"
import { ShoppingCart, Plus, Trash2, CheckSquare, Square } from "lucide-react"
import type { ShoppingItem } from "../types"

export default function Shopping() {
  const [newItem, setNewItem] = useState("")
  const qc = useQueryClient()

  const { data: items, isLoading } = useQuery({
    queryKey: ["shopping"],
    queryFn: fetchShopping,
  })

  const addMut = useMutation({
    mutationFn: addShoppingItem,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shopping"] })
      setNewItem("")
    },
  })

  const toggleMut = useMutation({
    mutationFn: toggleShoppingItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shopping"] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteShoppingItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shopping"] }),
  })

  const pending = items?.filter((i: ShoppingItem) => !i.is_bought) ?? []
  const bought = items?.filter((i: ShoppingItem) => i.is_bought) ?? []

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Shopping</h1>
          <p className="text-text-secondary text-sm">Manage your shopping list</p>
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        <Input
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          placeholder="Add an item..."
          onKeyDown={(e) => {
            if (e.key === "Enter" && newItem.trim()) {
              addMut.mutate({ name: newItem.trim() })
            }
          }}
        />
        <Button
          disabled={!newItem.trim() || addMut.isPending}
          onClick={() => addMut.mutate({ name: newItem.trim() })}
        >
          {addMut.isPending ? <Spinner size="sm" /> : <Plus className="w-4 h-4" />}
        </Button>
      </div>

      {isLoading ? (
        <Spinner className="py-12" />
      ) : !items?.length ? (
        <Card><p className="text-sm text-text-muted text-center py-8">Shopping list is empty</p></Card>
      ) : (
        <div className="space-y-2">
          <AnimatePresence>
            {pending.map((item: ShoppingItem) => (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
              >
                <Card className="flex items-center gap-3 py-3 px-4">
                  <button onClick={() => toggleMut.mutate(item.id)}>
                    <Square className="w-5 h-5 text-text-muted hover:text-text-secondary transition-colors" />
                  </button>
                  <span className="flex-1 text-sm">{item.name}</span>
                  {item.category && <Badge>{item.category}</Badge>}
                  <button
                    onClick={() => deleteMut.mutate(item.id)}
                    className="text-text-muted hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>

          {bought.length > 0 && (
            <>
              <p className="text-xs text-text-muted uppercase tracking-wider pt-4 pb-1">Already bought</p>
              <AnimatePresence>
                {bought.map((item: ShoppingItem) => (
                  <motion.div
                    key={item.id}
                    layout
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    <Card className="flex items-center gap-3 py-3 px-4">
                      <button onClick={() => toggleMut.mutate(item.id)}>
                        <CheckSquare className="w-5 h-5 text-emerald-400" />
                      </button>
                      <span className="flex-1 text-sm line-through text-text-muted">{item.name}</span>
                      {item.category && <Badge>{item.category}</Badge>}
                      <button
                        onClick={() => deleteMut.mutate(item.id)}
                        className="text-text-muted hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </Card>
                  </motion.div>
                ))}
              </AnimatePresence>
            </>
          )}
        </div>
      )}
    </motion.div>
  )
}
