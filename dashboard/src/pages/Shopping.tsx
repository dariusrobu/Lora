import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { fetchShopping, addShoppingItem, toggleShoppingItem, deleteShoppingItem } from "../api/queries/shopping"
import { Spinner } from "../components/ui/Spinner"
import { 
  Plus, Trash2, CheckSquare, Square, ShoppingBag, ShoppingCart, 
  Check, Sparkles, Tag, Filter, Circle, CheckCircle2 
} from "lucide-react"
import type { ShoppingItem } from "../types"

export default function Shopping() {
  const [newItem, setNewItem] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<string>("")
  const [activeFilter, setActiveFilter] = useState<string>("all")
  const [toggling, setToggling] = useState<Set<number>>(new Set())
  const qc = useQueryClient()

  const { data: items, isLoading, isError, refetch } = useQuery({
    queryKey: ["shopping"],
    queryFn: fetchShopping,
    refetchInterval: 30_000,
  })

  const addMut = useMutation({
    mutationFn: ({ item, category }: { item: string; category?: string }) => 
      addShoppingItem(item, category || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shopping"] })
      setNewItem("")
      setSelectedCategory("")
    },
  })

  const toggleMut = useMutation({
    mutationFn: toggleShoppingItem,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shopping"] })
      setTimeout(() => setToggling(new Set()), 300)
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteShoppingItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shopping"] }),
  })

  const handleToggle = (id: number) => {
    setToggling((prev) => new Set(prev).add(id))
    toggleMut.mutate(id)
  }

  const handleAdd = () => {
    if (!newItem.trim() || addMut.isPending) return
    addMut.mutate({ 
      item: newItem.trim(), 
      category: selectedCategory.trim() || undefined 
    })
  }

  const POPULAR_CATEGORIES = ["Alimente", "Casă", "Tech", "Farmacie", "Haine", "Altele"]

  const allCategories = useMemo(() => {
    const cats = new Set<string>()
    items?.forEach((i) => {
      if (i.category) cats.add(i.category)
    })
    return Array.from(cats)
  }, [items])

  const pending = useMemo(() => {
    let list = items?.filter((i: ShoppingItem) => !i.is_bought) ?? []
    if (activeFilter !== "all") {
      list = list.filter((i) => i.category?.toLowerCase() === activeFilter.toLowerCase())
    }
    return list
  }, [items, activeFilter])

  const bought = useMemo(() => {
    let list = items?.filter((i: ShoppingItem) => i.is_bought) ?? []
    if (activeFilter !== "all") {
      list = list.filter((i) => i.category?.toLowerCase() === activeFilter.toLowerCase())
    }
    return list
  }, [items, activeFilter])

  const totalCount = items?.length ?? 0
  const boughtCount = items?.filter((i) => i.is_bought).length ?? 0
  const pendingCount = totalCount - boughtCount
  const progressPct = totalCount > 0 ? Math.round((boughtCount / totalCount) * 100) : 0

  return (
    <motion.div 
      initial={{ opacity: 0, y: 8 }} 
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto space-y-6 pb-20"
    >
      {/* Header with Aurora Glow */}
      <div className="relative pt-2 pb-1">
        <div className="absolute -top-10 left-0 w-72 h-40 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <ShoppingBag className="w-4 h-4" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white">Cumpărături</h1>
            </div>
            <p className="text-zinc-400 text-xs sm:text-sm pl-10">
              {totalCount === 0 
                ? "Niciun articol în listă" 
                : `${pendingCount} articole rămase de cumpărat, ${boughtCount} finalizate`}
            </p>
          </div>
        </div>
      </div>

      {/* 3 Large Prominent Metrics */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4 p-4 rounded-3xl bg-white/[0.02] border border-white/[0.05] divide-x divide-white/[0.06] backdrop-blur-xl">
        <div className="flex flex-col items-center sm:items-start sm:pl-3">
          <div className="flex items-center gap-1.5 mb-1 text-zinc-400">
            <ShoppingCart className="w-4 h-4 text-indigo-400" />
            <span className="text-[11px] font-bold uppercase tracking-wider">De Luat</span>
          </div>
          <span className="text-3xl sm:text-4xl font-black text-white tabular-nums tracking-tight">
            {pendingCount}
          </span>
          <span className="text-[11px] text-zinc-500 mt-0.5">articole active</span>
        </div>

        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-zinc-400">
            <Check className="w-4 h-4 text-emerald-400" />
            <span className="text-[11px] font-bold uppercase tracking-wider">Cumpărate</span>
          </div>
          <span className="text-3xl sm:text-4xl font-black text-emerald-400 tabular-nums tracking-tight">
            {boughtCount}
          </span>
          <span className="text-[11px] text-zinc-500 mt-0.5">în coș</span>
        </div>

        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-zinc-400">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span className="text-[11px] font-bold uppercase tracking-wider">Progres</span>
          </div>
          <span className="text-3xl sm:text-4xl font-black text-amber-400 tabular-nums tracking-tight">
            {progressPct}%
          </span>
          <span className="text-[11px] text-zinc-500 mt-0.5">completat</span>
        </div>
      </div>

      {/* Progress Line */}
      {totalCount > 0 && (
        <div className="space-y-1.5 px-1">
          <div className="h-2 bg-white/[0.04] rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 shadow-[0_0_12px_rgba(99,102,241,0.4)]"
            />
          </div>
          <div className="flex justify-between text-[11px] text-zinc-500 font-medium">
            <span>{boughtCount} din {totalCount} articole bifate</span>
            {progressPct === 100 ? (
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <Check className="w-3 h-3" /> Listă completată!
              </span>
            ) : (
              <span>{100 - progressPct}% rămas</span>
            )}
          </div>
        </div>
      )}

      {/* Quick Add Bar (Linear Style) */}
      <div className="p-3.5 sm:p-4 rounded-3xl bg-white/[0.02] border border-white/[0.06] backdrop-blur-xl space-y-3">
        <div className="flex items-center gap-2">
          <input
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd()
            }}
            placeholder="Ce vrei să cumperi? (ex: Lapte ovăz, Cafea boabe...)"
            className="flex-1 bg-white/[0.03] hover:bg-white/[0.05] focus:bg-white/[0.07] border border-white/[0.08] focus:border-indigo-400/40 rounded-2xl py-2.5 px-4 text-sm text-white placeholder:text-zinc-500 outline-none transition-all"
          />
          <motion.button
            onClick={handleAdd}
            disabled={!newItem.trim() || addMut.isPending}
            whileTap={{ scale: 0.94 }}
            className="px-4 sm:px-5 py-2.5 rounded-2xl bg-gradient-to-tr from-primary to-accent text-white font-semibold text-xs disabled:opacity-30 transition-all flex items-center justify-center gap-2 shrink-0 shadow-[0_2px_14px_rgba(99,102,241,0.35)] hover:scale-[1.02]"
          >
            {addMut.isPending ? (
              <Spinner size="sm" />
            ) : (
              <>
                <Plus className="w-4 h-4" />
                <span className="hidden sm:inline">Adaugă</span>
              </>
            )}
          </motion.button>
        </div>

        {/* Category Pills Selector */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar">
          <span className="text-zinc-500 text-[11px] font-medium flex items-center gap-1 mr-1 shrink-0">
            <Tag className="w-3 h-3" /> Categorie:
          </span>
          {POPULAR_CATEGORIES.map((cat) => {
            const isSelected = selectedCategory.toLowerCase() === cat.toLowerCase()
            return (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(isSelected ? "" : cat)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-all shrink-0 ${
                  isSelected
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40"
                    : "bg-white/[0.03] text-zinc-400 hover:text-white hover:bg-white/[0.06] border border-white/[0.04]"
                }`}
              >
                {cat}
              </button>
            )
          })}
        </div>
      </div>

      {/* Category Filter Pills (if categories exist) */}
      {allCategories.length > 0 && (
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 no-scrollbar">
          <Filter className="w-3.5 h-3.5 text-zinc-500 mr-1 shrink-0" />
          <button
            onClick={() => setActiveFilter("all")}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition-all shrink-0 ${
              activeFilter === "all"
                ? "bg-white text-black shadow-sm"
                : "bg-white/[0.03] text-zinc-400 hover:text-white border border-white/[0.05]"
            }`}
          >
            Toate ({totalCount})
          </button>
          {allCategories.map((cat: string) => {
            const count = items?.filter((i: ShoppingItem) => i.category?.toLowerCase() === cat.toLowerCase()).length ?? 0
            const isSelected = activeFilter.toLowerCase() === cat.toLowerCase()
            return (
              <button
                key={cat}
                onClick={() => setActiveFilter(cat)}
                className={`px-3 py-1 rounded-full text-xs font-semibold transition-all shrink-0 ${
                  isSelected
                    ? "bg-indigo-500 text-white shadow-sm"
                    : "bg-white/[0.03] text-zinc-400 hover:text-white border border-white/[0.05]"
                }`}
              >
                {cat} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Items Section */}
      {isLoading ? (
        <div className="py-20 flex items-center justify-center">
          <Spinner className="w-8 h-8 text-indigo-400" />
        </div>
      ) : isError ? (
        <div className="py-12 text-center rounded-3xl bg-rose-500/[0.03] border border-rose-500/10">
          <p className="text-sm text-rose-300 mb-3">Eroare la încărcarea listei de cumpărături.</p>
          <button
            onClick={() => refetch()}
            className="px-4 py-1.5 rounded-xl bg-rose-500/20 text-rose-300 text-xs font-semibold hover:bg-rose-500/30 transition-all"
          >
            Reîncearcă
          </button>
        </div>
      ) : totalCount === 0 ? (
        <div className="py-16 text-center rounded-3xl bg-white/[0.015] border border-white/[0.04]">
          <div className="w-12 h-12 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto mb-3 text-zinc-400">
            <ShoppingCart className="w-5 h-5 text-indigo-400" />
          </div>
          <p className="text-sm font-semibold text-white mb-1">Lista de cumpărături este goală</p>
          <p className="text-xs text-zinc-500 max-w-xs mx-auto">
            Adaugă articole folosind bara de mai sus sau spune-i Lorei pe Telegram ce ai nevoie.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Pending items */}
          {pending.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between px-1 mb-2">
                <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Circle className="w-3 h-3 text-indigo-400" /> De cumpărat ({pending.length})
                </span>
              </div>
              <AnimatePresence mode="popLayout">
                {pending.map((item: ShoppingItem, idx: number) => {
                  const isToggling = toggling.has(item.id)
                  return (
                    <motion.div
                      key={item.id}
                      layout
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ delay: idx * 0.02 }}
                      className="group flex items-center justify-between p-3 rounded-2xl bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.04] hover:border-white/[0.08] transition-all"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        {/* Magnetic Checkbox */}
                        <motion.button
                          whileTap={{ scale: 0.8 }}
                          onClick={() => handleToggle(item.id)}
                          className="w-6 h-6 rounded-full border border-white/20 group-hover:border-emerald-400 group-hover:bg-emerald-500/10 flex items-center justify-center shrink-0 transition-colors"
                        >
                          {isToggling ? (
                            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                            </motion.div>
                          ) : (
                            <Circle className="w-3.5 h-3.5 text-transparent group-hover:text-emerald-400/50 transition-colors" />
                          )}
                        </motion.button>

                        <span className={`text-sm font-medium transition-colors truncate ${
                          isToggling ? "text-zinc-500 line-through" : "text-zinc-100 group-hover:text-white"
                        }`}>
                          {item.item}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0 ml-2">
                        {item.category && (
                          <span className="px-2.5 py-0.5 rounded-full bg-white/[0.04] text-[11px] font-medium text-zinc-400 border border-white/[0.04]">
                            {item.category}
                          </span>
                        )}
                        <button
                          onClick={() => deleteMut.mutate(item.id)}
                          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                          title="Șterge"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </div>
          )}

          {/* Already Bought Items */}
          {bought.length > 0 && (
            <div className="space-y-1.5 pt-4">
              <div className="flex items-center justify-between px-1 mb-2">
                <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400/70" /> Cumpărate deja ({bought.length})
                </span>
              </div>
              <AnimatePresence mode="popLayout">
                {bought.map((item: ShoppingItem) => (
                  <motion.div
                    key={item.id}
                    layout
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="group flex items-center justify-between p-2.5 rounded-2xl bg-white/[0.01] hover:bg-white/[0.025] border border-white/[0.02] hover:border-white/[0.05] transition-all"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <motion.button
                        whileTap={{ scale: 0.8 }}
                        onClick={() => toggleMut.mutate(item.id)}
                        className="w-6 h-6 rounded-full flex items-center justify-center shrink-0"
                      >
                        <CheckCircle2 className="w-5 h-5 text-emerald-400/80 group-hover:text-emerald-300 transition-colors" />
                      </motion.button>
                      <span className="text-sm line-through text-zinc-500 truncate group-hover:text-zinc-400 transition-colors">
                        {item.item}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 ml-2">
                      {item.category && (
                        <span className="px-2 py-0.5 rounded-full bg-white/[0.02] text-[10px] font-medium text-zinc-500">
                          {item.category}
                        </span>
                      )}
                      <button
                        onClick={() => deleteMut.mutate(item.id)}
                        className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                        title="Șterge"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}
