import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { fetchShopping, addShoppingItem, toggleShoppingItem } from "../../api/queries/shopping"
import { WidgetCard } from "./WidgetCard"
import { ShoppingCart, Plus, CheckCircle2, Circle, Check, Sparkles } from "lucide-react"

interface Props { onExpand?: () => void }

export function ShoppingWidget({ onExpand }: Props) {
  const [quickItem, setQuickItem] = useState("")
  const [toggling, setToggling] = useState<Set<number>>(new Set())
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shopping"] })
      setTimeout(() => setToggling(new Set()), 350)
    },
  })

  const pending = useMemo(() => items?.filter((i) => !i.is_bought) ?? [], [items])
  const bought = useMemo(() => items?.filter((i) => i.is_bought) ?? [], [items])
  const total = items?.length ?? 0
  const pct = total > 0 ? Math.round((bought.length / total) * 100) : 0
  const hasData = total > 0

  const handleToggle = (id: number) => {
    setToggling((prev) => new Set(prev).add(id))
    toggleMut.mutate(id)
  }

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
      emptyMessage="Lista de cumpărături este goală"
      emptyCTA={
        <div className="flex gap-2 w-full max-w-xs mt-2">
          <input
            value={quickItem}
            onChange={(e) => setQuickItem(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
            placeholder="Adaugă un articol..."
            autoFocus
            className="flex-1 bg-white/[0.03] border border-white/[0.08] focus:border-indigo-400/40 rounded-xl py-2 px-3 text-xs text-white placeholder:text-zinc-500 outline-none transition-all"
          />
          <button
            onClick={handleQuickAdd}
            disabled={!quickItem.trim() || addMut.isPending}
            className="px-3 py-2 rounded-xl bg-gradient-to-tr from-primary to-accent text-white font-bold text-xs disabled:opacity-40 transition-all flex items-center justify-center shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      }
    >
      {/* 3 Prominent Metrics */}
      <div className="grid grid-cols-3 gap-3 p-3 rounded-2xl bg-white/[0.015] border border-white/[0.04] mb-4 divide-x divide-white/[0.06]">
        {/* Items to buy */}
        <div className="flex flex-col items-center sm:items-start sm:pl-2">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <ShoppingCart className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">De Luat</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-white tabular-nums tracking-tight">
            {pending.length}
          </span>
        </div>

        {/* Bought Items */}
        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <Check className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Cumpărate</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-emerald-400 tabular-nums tracking-tight">
            {bought.length}
          </span>
        </div>

        {/* Progress % */}
        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Progres</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-amber-400 tabular-nums tracking-tight">
            {pct}%
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      {total > 0 && (
        <div className="space-y-1 mb-4">
          <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400"
            />
          </div>
          <div className="flex justify-between text-[10px] text-zinc-500 font-medium">
            <span>{bought.length} din {total} cumpărate</span>
            {pct === 100 && <span className="text-emerald-400 font-semibold">Listă completă!</span>}
          </div>
        </div>
      )}

      {/* Pending Items List (Fluid & Magnetic Checkboxes) */}
      {pending.length > 0 ? (
        <div className="space-y-1 mb-4">
          {pending.slice(0, 5).map((item, idx) => {
            const isToggling = toggling.has(item.id)
            return (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className="group flex items-center justify-between p-2 rounded-xl hover:bg-white/[0.035] border border-transparent hover:border-white/[0.04] transition-all"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  {/* Magnetic Check Button */}
                  <motion.button
                    whileTap={{ scale: 0.85 }}
                    onClick={() => handleToggle(item.id)}
                    className="w-5 h-5 rounded-full border border-white/20 group-hover:border-emerald-400 group-hover:bg-emerald-500/10 flex items-center justify-center shrink-0 transition-colors"
                  >
                    {isToggling ? (
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      </motion.div>
                    ) : (
                      <Circle className="w-3 h-3 text-transparent group-hover:text-emerald-400/40 transition-colors" />
                    )}
                  </motion.button>

                  <span className={`text-xs font-medium truncate transition-colors ${
                    isToggling ? "text-zinc-500 line-through" : "text-zinc-200 group-hover:text-white"
                  }`}>
                    {item.item}
                  </span>
                </div>

                {item.category && (
                  <span className="px-2 py-0.5 rounded-full bg-white/[0.04] text-[10px] font-medium text-zinc-400 shrink-0 ml-2">
                    {item.category}
                  </span>
                )}
              </motion.div>
            )
          })}
          {pending.length > 5 && (
            <p className="text-[11px] text-zinc-500 pl-3 pt-0.5">
              +{pending.length - 5} articole în plus
            </p>
          )}
        </div>
      ) : hasData ? (
        <div className="py-4 text-center text-xs text-emerald-400 flex items-center justify-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5" /> Toate cumpărăturile au fost făcute!
        </div>
      ) : null}

      {/* Quick Add Bar (Linear Style) */}
      <div className="flex items-center gap-2 pt-2 border-t border-white/[0.05]">
        <input
          value={quickItem}
          onChange={(e) => setQuickItem(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleQuickAdd() }}
          placeholder="Adaugă articol de cumpărat..."
          className="flex-1 bg-white/[0.03] hover:bg-white/[0.05] focus:bg-white/[0.06] border border-white/[0.08] focus:border-indigo-400/40 rounded-xl py-2 px-3.5 text-xs text-white placeholder:text-zinc-500 outline-none transition-all"
        />
        <motion.button
          onClick={handleQuickAdd}
          disabled={!quickItem.trim() || addMut.isPending}
          whileTap={{ scale: 0.95 }}
          className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary to-accent text-white disabled:opacity-30 transition-all flex items-center justify-center shrink-0 shadow-[0_2px_12px_rgba(99,102,241,0.3)] hover:scale-105"
        >
          <Plus className="w-4 h-4" />
        </motion.button>
      </div>
    </WidgetCard>
  )
}
