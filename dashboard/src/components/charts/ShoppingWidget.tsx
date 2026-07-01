import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchShopping, addShoppingItem, toggleShoppingItem } from "../../api/queries/shopping"
import { WidgetCard } from "./WidgetCard"
import { ShoppingCart, Plus, CheckCircle2, Circle } from "lucide-react"

interface Props { onExpand?: () => void }

export function ShoppingWidget({ onExpand }: Props) {
  const [quickItem, setQuickItem] = useState("")
  const qc = useQueryClient()

  const { data: items, isLoading, isError, refetch } = useQuery({
    queryKey: ["shopping"],
    queryFn: fetchShopping,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const addMut = useMutation({
    mutationFn: (item: string) => addShoppingItem(item),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shopping"] })
      setQuickItem("")
    },
  })
  const toggleMut = useMutation({
    mutationFn: toggleShoppingItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shopping"] }),
  })

  const pending = items?.filter((i) => !i.is_bought) ?? []
  const bought = items?.filter((i) => i.is_bought) ?? []
  const total = items?.length ?? 0
  const hasData = total > 0

  const handleQuickAdd = () => {
    if (!quickItem.trim() || addMut.isPending) return
    addMut.mutate(quickItem.trim())
  }

  return (
    <WidgetCard
      icon={<ShoppingCart className="w-4 h-4" />}
      label="Shopping"
      linkTo="/shopping"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="Shopping list empty"
      emptyCTA={
        <div className="flex gap-1.5 w-full max-w-64">
          <input value={quickItem} onChange={(e) => setQuickItem(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
            placeholder="Add item..." autoFocus
            className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors" />
          <button onClick={handleQuickAdd} disabled={!quickItem.trim() || addMut.isPending}
            className="w-8 h-8 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0">
            <Plus className="w-4 h-4" />
          </button>
        </div>
      }
    >
      {/* Hero — remaining count */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl font-bold text-text-primary">{pending.length}</span>
        <span className="text-xs text-text-secondary">items left · {bought.length}/{total} bought</span>
      </div>

      {/* Pending items — quick toggle */}
      {pending.length > 0 && (
        <div className="space-y-0.5 mb-3">
          {pending.slice(0, 5).map((item) => (
            <motion.button key={item.id} onClick={() => toggleMut.mutate(item.id)}
              whileTap={{ scale: 0.97 }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/10 dark:hover:bg-white/[0.04] transition-colors text-left group">
              <Circle className="w-3.5 h-3.5 text-text-muted shrink-0 group-hover:text-primary transition-colors" />
              <span className="text-xs text-text-primary truncate flex-1">{item.item}</span>
              {item.category && <span className="text-[9px] text-text-muted">{item.category}</span>}
            </motion.button>
          ))}
          {pending.length > 5 && (
            <p className="text-[10px] text-text-muted pl-2">+{pending.length - 5} more</p>
          )}
        </div>
      )}

      {/* Quick add */}
      <div className="flex gap-1.5">
        <input value={quickItem} onChange={(e) => setQuickItem(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
          placeholder="Add item..."
          className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 transition-colors" />
        <button onClick={handleQuickAdd} disabled={!quickItem.trim() || addMut.isPending}
          className="w-8 h-8 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0">
          <Plus className="w-4 h-4" />
        </button>
      </div>
    </WidgetCard>
  )
}
