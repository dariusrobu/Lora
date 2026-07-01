import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { twMerge } from "tailwind-merge"
import { fetchFinanceHistory, fetchFinanceSummary, createTransaction } from "../../api/queries/finance"
import { WidgetCard } from "./WidgetCard"
import { Spinner } from "../ui/Spinner"
import { Wallet, Plus, TrendingUp, TrendingDown } from "lucide-react"

interface Props { onExpand?: () => void }

const EXPENSE_CATEGORIES = ["Food", "Transport", "Utilities", "Entertainment", "Shopping", "Health", "Other"]

const CATEGORY_COLORS: Record<string, string> = {
  Food: "bg-orange-500",
  Transport: "bg-blue-500",
  Utilities: "bg-yellow-500",
  Entertainment: "bg-purple-500",
  Shopping: "bg-pink-500",
  Health: "bg-emerald-500",
  Other: "bg-gray-500",
}

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("ro-RO", { style: "currency", currency: "RON", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n)
}

export function FinanceWidget({ onExpand }: Props) {
  const [showQuickExpense, setShowQuickExpense] = useState(false)
  const [expAmount, setExpAmount] = useState("")
  const [expDesc, setExpDesc] = useState("")
  const [expCategory, setExpCategory] = useState("Food")
  const qc = useQueryClient()

  const { data: summary, isLoading: sumLoading, isError: sumErr, refetch: refetchSum } = useQuery({
    queryKey: ["finance-summary"],
    queryFn: fetchFinanceSummary,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
  const { data: history, isLoading: histLoading, isError: histErr, refetch: refetchHist } = useQuery({
    queryKey: ["finance-history", 14],
    queryFn: () => fetchFinanceHistory(14),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const addExpMut = useMutation({
    mutationFn: createTransaction,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance-summary"] })
      qc.invalidateQueries({ queryKey: ["finance-history"] })
      setShowQuickExpense(false)
      setExpAmount("")
      setExpDesc("")
      setExpCategory("Food")
    },
  })

  const isLoading = sumLoading || histLoading
  const isError = sumErr || histErr
  const bal = summary?.summary?.balance ?? 0
  const inc = summary?.summary?.income ?? 0
  const exp = summary?.summary?.expense ?? 0
  const hasData = (history?.length ?? 0) > 0 || bal > 0

  // Budget bar
  const dailyMap = new Map<string, { income: number; expense: number }>()
  for (const tx of history ?? []) {
    if (!dailyMap.has(tx.transaction_date)) dailyMap.set(tx.transaction_date, { income: 0, expense: 0 })
    const d = dailyMap.get(tx.transaction_date)!
    if (tx.type === "income") d.income += tx.amount
    else d.expense += tx.amount
  }
  const incTotal = Array.from(dailyMap.values()).reduce((s, d) => s + d.income, 0)
  const expTotal = Array.from(dailyMap.values()).reduce((s, d) => s + d.expense, 0)
  const budgetPct = incTotal > 0 ? Math.min(Math.round((expTotal / incTotal) * 100), 100) : 0

  // Trend: compare last 7 days vs previous 7 days
  const trend = useMemo(() => {
    if (!history || history.length < 2) return null
    const now = new Date()
    const threshold = new Date(now); threshold.setDate(threshold.getDate() - 7)
    const older = new Date(now); older.setDate(older.getDate() - 14)
    const recent = history.filter((t) => {
      const d = new Date(t.transaction_date + "T00:00:00")
      return d >= threshold && d <= now
    })
    const previous = history.filter((t) => {
      const d = new Date(t.transaction_date + "T00:00:00")
      return d >= older && d < threshold
    })
    const rExp = recent.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0)
    const pExp = previous.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0)
    if (pExp === 0) return null
    const change = Math.round(((rExp - pExp) / pExp) * 100)
    return change
  }, [history])

  // Category breakdown for expenses
  const categoryTotals = useMemo(() => {
    const map = new Map<string, number>()
    for (const tx of history ?? []) {
      if (tx.type === "expense") {
        map.set(tx.category, (map.get(tx.category) ?? 0) + tx.amount)
      }
    }
    const total = Array.from(map.values()).reduce((s, v) => s + v, 0)
    return Array.from(map.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, 3)
      .map(([cat, amt]) => ({ category: cat, amount: amt, pct: total > 0 ? Math.round((amt / total) * 100) : 0 }))
  }, [history])

  const handleLogExpense = () => {
    if (!expAmount.trim() || addExpMut.isPending) return
    addExpMut.mutate({
      amount: Number(expAmount),
      description: expDesc.trim() || "Quick expense",
      category: expCategory,
      type: "expense",
    })
  }

  return (
    <WidgetCard
      icon={<Wallet className="w-4 h-4" />}
      label="Finance"
      linkTo="/finance"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={() => { refetchSum(); refetchHist() }}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="No transactions yet"
      emptyCTA={
        <motion.div whileTap={{ scale: 0.97 }}>
          <button onClick={() => setShowQuickExpense(true)}
            className="inline-block px-4 py-1.5 rounded-full glass-strong text-apple-caption2 font-medium text-primary hover:bg-primary/10 transition-all">
            Add transaction
          </button>
        </motion.div>
      }
    >
      {/* Hero — animated balance + trend */}
      <div className="flex items-end justify-between mb-3">
        <div>
          <p className="text-apple-caption2 text-text-muted">Balance</p>
          <div className="flex items-center gap-2">
            <motion.p key={bal} initial={{ y: -8, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
              className="text-2xl font-bold text-text-primary tabular-nums">{fmtCurrency(bal)}</motion.p>
            {trend !== null && (
              <motion.div key={trend} initial={{ scale: 0 }} animate={{ scale: 1 }}
                className={`flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                  trend <= 0 ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-red-500/10 text-red-500"
                }`}>
                {trend <= 0 ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                {Math.abs(trend)}%
              </motion.div>
            )}
          </div>
        </div>
        <motion.button
          onClick={() => setShowQuickExpense((p) => !p)}
          whileTap={{ scale: 0.9 }}
          className="w-9 h-9 rounded-full bg-amber-500 text-white flex items-center justify-center shadow-lg"
        >
          <Plus className="w-4 h-4" />
        </motion.button>
      </div>

      {/* Budget bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-text-muted">Spent of income</span>
          <span className="text-text-primary font-medium tabular-nums">{fmtCurrency(expTotal)} / {fmtCurrency(incTotal)}</span>
        </div>
        <motion.div className="h-1.5 bg-white/40 dark:bg-white/[0.06] rounded-full overflow-hidden">
          <motion.div className="h-full rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${budgetPct}%` }}
            transition={{ duration: 0.8, ease: [0.34, 1.56, 0.64, 1] }}
            style={{ background: budgetPct > 80 ? "#FF3B30" : "linear-gradient(90deg, #7c3aed, #a78bfa)" }} />
        </motion.div>
      </div>

      {/* Category mini bar (top 3 expense categories) */}
      {categoryTotals.length > 0 && incTotal > 0 && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mb-3">
          <div className="flex h-1.5 rounded-full overflow-hidden gap-0.5">
            {categoryTotals.map(({ category, pct }) => (
              <motion.div key={category} initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className={twMerge("h-full rounded-full", CATEGORY_COLORS[category] ?? "bg-gray-500")}
                title={`${category}: ${pct}%`} />
            ))}
          </div>
          <div className="flex gap-3 mt-1.5">
            {categoryTotals.map(({ category, amount, pct }) => (
              <div key={category} className="flex items-center gap-1 text-[9px] text-text-muted">
                <span className={twMerge("w-1.5 h-1.5 rounded-full", CATEGORY_COLORS[category] ?? "bg-gray-500")} />
                {category} {pct}%
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Quick expense form */}
      {showQuickExpense && (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
          className="overflow-hidden mb-3">
          <div className="space-y-1.5">
            <div className="flex gap-1.5">
              <input value={expDesc} onChange={(e) => setExpDesc(e.target.value)}
                placeholder="What for..." autoFocus
                className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 focus:ring-2 focus:ring-primary/20 transition-all" />
              <select value={expCategory} onChange={(e) => setExpCategory(e.target.value)}
                className="bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-2 text-xs text-text-primary outline-none focus:border-primary/30 focus:ring-2 focus:ring-primary/20 transition-all">
                {EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="flex gap-1.5">
              <input value={expAmount} onChange={(e) => setExpAmount(e.target.value)} type="number"
                placeholder="Amount"
                className="flex-1 bg-white/60 dark:bg-white/[0.06] border border-border rounded-xl py-2 px-3 text-xs text-text-primary placeholder:text-text-muted outline-none focus:border-primary/30 focus:ring-2 focus:ring-primary/20 transition-all tabular-nums" />
              <button onClick={handleLogExpense} disabled={!expAmount.trim() || addExpMut.isPending}
                className="w-9 h-9 rounded-full bg-amber-500 text-white disabled:opacity-40 transition-opacity flex items-center justify-center shrink-0 shadow-lg">
                {addExpMut.isPending ? <Spinner size="sm" /> : <Plus className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Recent mini-list — staggered */}
      {history && history.length > 0 && (
        <div className="space-y-0.5">
          {history.slice(0, 4).map((tx, idx) => (
            <motion.div key={tx.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.04, duration: 0.2 }}
              className="flex items-center justify-between px-2 py-1 rounded-lg hover:bg-white/10 dark:hover:bg-white/[0.04] transition-colors">
              <div className="flex items-center gap-2 min-w-0">
                <div className={twMerge("w-1.5 h-1.5 rounded-full shrink-0", tx.type === "income" ? "bg-emerald-500" : "bg-red-500")} />
                <span className="text-[11px] text-text-primary truncate">{tx.description || tx.category}</span>
              </div>
              <span className={twMerge("text-[11px] shrink-0 ml-2 tabular-nums", tx.type === "income" ? "text-emerald-500" : "text-red-500")}>
                {tx.type === "income" ? "+" : "-"}{fmtCurrency(tx.amount)}
              </span>
            </motion.div>
          ))}
        </div>
      )}
    </WidgetCard>
  )
}
