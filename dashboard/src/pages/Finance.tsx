import { useState, useMemo, useEffect, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import {
  fetchFinanceSummary,
  fetchFinanceHistory,
  createTransaction,
  deleteTransaction,
  fetchProductMemories,
  deleteProductMemory,
  fetchMerchantMemories,
  deleteMerchantMemory,
  fetchCategoryTransactions,
  updateFinanceBudget,
} from "../api/queries/finance"
import { Card } from "../components/ui/Card"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { Spinner } from "../components/ui/Spinner"
import { PageHeader, ModeSelector, Metric } from "../components/ui"
import {
  Wallet,
  Plus,
  Trash2,
  TrendingUp,
  TrendingDown,
  Store,
  Search,
  PieChart as PieIcon,
  Sparkles,
  Layers,
} from "lucide-react"
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts"
import type { Transaction, ProductMemory, MerchantMemory } from "../types"

const DONUT_COLORS = [
  "#6366f1", // Indigo
  "#ec4899", // Pink
  "#f59e0b", // Amber
  "#10b981", // Emerald
  "#06b6d4", // Cyan
  "#8b5cf6", // Violet
  "#f43f5e", // Rose
  "#3b82f6", // Blue
  "#84cc16", // Lime
]

function formatCurrency(n: number) {
  return new Intl.NumberFormat("ro-RO", { style: "currency", currency: "RON", minimumFractionDigits: 2 }).format(n)
}

function formatChartAmount(n: number) {
  return new Intl.NumberFormat("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
}

function formatTransactionDate(value?: string) {
  if (!value) return "Dată necunoscută"
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? "Dată necunoscută" : parsed.toLocaleDateString("ro-RO", { day: "numeric", month: "short" })
}

export default function Finance() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<"transactions" | "memory">("transactions")
  const [showModal, setShowModal] = useState(() => searchParams.get("action") === "add")
  const [amount, setAmount] = useState("")
  const [category, setCategory] = useState("")
  const [type, setType] = useState<"income" | "expense">("expense")
  const [description, setDescription] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [budgetCategory, setBudgetCategory] = useState("Total")
  const [budgetAmount, setBudgetAmount] = useState("")
  const [budgetPeriod, setBudgetPeriod] = useState<"weekly" | "monthly">("monthly")
  const [showBudgets, setShowBudgets] = useState(false)
  const categoryPanelRef = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()

  useEffect(() => {
    if (searchParams.get("action") !== "add") return
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (!selectedCategory) return
    requestAnimationFrame(() => categoryPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }))
  }, [selectedCategory])

  const { data: summary } = useQuery({
    queryKey: ["finance", "summary"],
    queryFn: fetchFinanceSummary,
  })

  const { data: transactions, isLoading: txLoading } = useQuery<Transaction[]>({
    queryKey: ["finance", "history"],
    queryFn: () => fetchFinanceHistory(30),
  })

  const categorySummary = summary?.categories
  const normalizeCategory = (value: string | undefined) => (value ?? "").trim().toLocaleLowerCase("ro-RO")
  const { data: categoryTransactions, isLoading: categoryLoading, isError: categoryError } = useQuery<Transaction[]>({
    queryKey: ["finance", "category", selectedCategory],
    queryFn: () => fetchCategoryTransactions(selectedCategory ?? ""),
    enabled: Boolean(selectedCategory),
  })
  const fallbackCategoryTransactions = (transactions ?? []).filter((txn) => normalizeCategory(txn.category) === normalizeCategory(selectedCategory ?? ""))

  const { data: productMemories, isLoading: prodLoading } = useQuery<ProductMemory[]>({
    queryKey: ["finance", "product-memories"],
    queryFn: fetchProductMemories,
    enabled: activeTab === "memory",
  })

  const { data: merchantMemories, isLoading: merchLoading } = useQuery<MerchantMemory[]>({
    queryKey: ["finance", "merchant-memories"],
    queryFn: fetchMerchantMemories,
    enabled: activeTab === "memory",
  })

  const deleteMut = useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] })
    },
  })

  const deleteProdMut = useMutation({
    mutationFn: deleteProductMemory,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance", "product-memories"] })
    },
  })

  const deleteMerchMut = useMutation({
    mutationFn: deleteMerchantMemory,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance", "merchant-memories"] })
    },
  })

  const createMut = useMutation({
    mutationFn: createTransaction,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] })
      setShowModal(false)
      setAmount("")
      setCategory("")
      setDescription("")
    },
  })

  const budgetMut = useMutation({
    mutationFn: updateFinanceBudget,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] })
      setBudgetAmount("")
    },
  })

  const handleSubmit = () => {
    const parsed = parseFloat(amount)
    if (!isNaN(parsed) && parsed > 0) {
      createMut.mutate({ amount: parsed, category, type, description })
    }
  }

  // Category breakdown for chart
  const categoriesData = useMemo(() => {
    if (!categorySummary?.length) return []
    return categorySummary.map((c) => ({
      name: c.category || "Altele",
      value: c.total,
    }))
  }, [categorySummary])

  const totalCategoryExpense = useMemo(() => {
    return categoriesData.reduce((acc, c) => acc + c.value, 0)
  }, [categoriesData])

  // Filtered product memories
  const filteredProducts = useMemo(() => {
    if (!productMemories) return []
    if (!searchQuery.trim()) return productMemories
    const q = searchQuery.toLowerCase()
    return productMemories.filter(
      (p) =>
        p.clean_name.toLowerCase().includes(q) ||
        p.raw_pattern.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        (p.merchant && p.merchant.toLowerCase().includes(q))
    )
  }, [productMemories, searchQuery])

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <PageHeader eyebrow="Spatial OS · Finance" title="Finanțe" description="Balanță, tranzacții și memoria bonurilor." action={<div className="flex items-center gap-2"><ModeSelector value={activeTab} options={[{ value: "transactions" as const, label: "Tranzacții" }, { value: "memory" as const, label: "Memorie bonuri" }]} onChange={setActiveTab} /><Button onClick={() => setShowModal(true)}><Plus className="h-4 w-4" /> Adaugă</Button></div>} />

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Metric label="Venituri lună" value={summary ? formatCurrency(summary.summary?.income ?? 0) : "—"} className="border-emerald-500/20" />
        <Metric label="Cheltuieli lună" value={summary ? formatCurrency(summary.summary?.expense ?? 0) : "—"} className="border-rose-500/20" />
        <Metric label="Balanță" value={summary ? formatCurrency(summary.summary?.balance ?? 0) : "—"} className={(summary?.summary?.balance ?? 0) >= 0 ? "border-emerald-500/20" : "border-rose-500/20"} />
        {/* Detailed visual cards remain below for the transaction context. */}
        <Card className="hidden py-4 px-5 border-white/[0.08] hover:border-emerald-500/30 transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Venituri Lună</span>
            <div className="w-8 h-8 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 flex items-center justify-center shadow-glow-emerald">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl sm:text-4xl font-black tabular-nums text-white">
            {summary ? formatCurrency(summary.summary?.income ?? 0) : "—"}
          </p>
        </Card>

        <Card className="hidden py-4 px-5 border-white/[0.08] hover:border-rose-500/30 transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Cheltuieli Lună</span>
            <div className="w-8 h-8 rounded-xl bg-rose-500/15 text-rose-400 border border-rose-500/25 flex items-center justify-center shadow-glow-rose">
              <TrendingDown className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl sm:text-4xl font-black tabular-nums text-rose-400">
            {summary ? formatCurrency(summary.summary?.expense ?? 0) : "—"}
          </p>
        </Card>

        <Card className={`hidden py-4 px-5 transition-all ${
          (summary?.summary?.balance ?? 0) < 0
            ? "border-rose-500/35 bg-rose-500/[0.05] shadow-glow-rose"
            : (summary?.summary?.balance ?? 0) > 0
            ? "border-emerald-500/35 bg-emerald-500/[0.05] shadow-glow-emerald"
            : "border-white/[0.08]"
        }`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-xs font-semibold uppercase tracking-wider ${
              (summary?.summary?.balance ?? 0) < 0 ? "text-rose-400" : (summary?.summary?.balance ?? 0) > 0 ? "text-emerald-400" : "text-text-secondary"
            }`}>
              {(summary?.summary?.balance ?? 0) < 0 ? "Deficit (Pe Minus)" : "Balanță Lună"}
            </span>
            <div className={`w-8 h-8 rounded-xl flex items-center justify-center border ${
              (summary?.summary?.balance ?? 0) < 0 
                ? "bg-rose-500/15 text-rose-400 border-rose-500/25 shadow-glow-rose" 
                : "bg-primary/15 text-primary border-primary/25 shadow-glow-indigo"
            }`}>
              <Wallet className="w-4 h-4" />
            </div>
          </div>
          <p className={`text-3xl sm:text-4xl font-black tabular-nums ${
            (summary?.summary?.balance ?? 0) < 0
              ? "text-rose-400"
              : (summary?.summary?.balance ?? 0) > 0
              ? "text-emerald-400"
              : "text-white"
          }`}>
            {summary ? formatCurrency(summary.summary?.balance ?? 0) : "—"}
          </p>
          {summary?.summary?.total_balance !== undefined && (
            <p className="text-[11px] text-text-muted mt-1.5 flex items-center justify-between border-t border-white/[0.06] pt-1.5">
              <span>Balanță totală</span>
              <span className={`font-bold tabular-nums ${
                summary.summary.total_balance < 0
                  ? "text-rose-400"
                  : summary.summary.total_balance > 0
                  ? "text-emerald-400"
                  : "text-text-secondary"
              }`}>
                {formatCurrency(summary.summary.total_balance)}
              </span>
            </p>
          )}
        </Card>
      </div>

      {/* Tab: TRANSACTIONS */}
      {activeTab === "transactions" && (
        <div className="space-y-6">
          {/* Category Spending Breakdown Chart */}
          {categoriesData.length > 0 && (
            <div className="glass-strong rounded-2xl p-5 shadow-apple-heavy">
              <div className="flex items-center gap-2 mb-4">
                <PieIcon className="w-4 h-4 text-primary" />
                <h3 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">
                  Cheltuieli pe Categorii (Luna Curentă)
                </h3>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
                {/* Donut Chart */}
                <div className="relative flex h-64 items-center justify-center sm:h-72 lg:col-span-5">
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-10">
                    <span className="text-[10px] uppercase font-semibold text-text-muted tracking-widest">Total Cheltuit</span>
                    <span className="max-w-[132px] truncate text-center text-[clamp(0.9rem,4vw,1.25rem)] font-black text-text-primary tabular-nums tracking-tight">
                      {formatChartAmount(totalCategoryExpense)}
                    </span>
                    <span className="text-[9px] font-semibold uppercase tracking-wider text-text-muted">RON</span>
                  </div>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "rgba(12, 12, 20, 0.92)",
                          backdropFilter: "blur(16px)",
                          border: "1px solid rgba(255,255,255,0.12)",
                          borderRadius: "12px",
                          fontSize: "11px",
                          boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
                        }}
                        formatter={(val: any) => [formatCurrency(Number(val) || 0), "Cheltuit"]}
                      />
                      <Pie
                        data={categoriesData}
                        cx="50%"
                        cy="50%"
                        innerRadius={68}
                        outerRadius={104}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {categoriesData.map((_, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={DONUT_COLORS[index % DONUT_COLORS.length]}
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Category List with Badges & Percentages */}
                <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-h-56 overflow-y-auto pr-1">
                  {categoriesData.map((cat, idx) => {
                    const pct = totalCategoryExpense > 0 ? Math.round((cat.value / totalCategoryExpense) * 100) : 0
                    const color = DONUT_COLORS[idx % DONUT_COLORS.length]
                    return (
                      <button
                        key={cat.name}
                        type="button"
                        onClick={() => setSelectedCategory(cat.name)}
                        className="flex w-full cursor-pointer items-center justify-between rounded-xl border border-border/40 bg-white/[0.03] p-2 text-left text-xs transition-colors hover:border-primary/40 hover:bg-primary/[0.06] active:bg-primary/[0.1]"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: color }}
                          />
                          <span className="font-medium text-text-primary capitalize truncate">{cat.name}</span>
                        </div>
                        <div className="flex items-center gap-2 text-text-secondary shrink-0 tabular-nums">
                          <span className="max-w-[48%] break-words text-right font-bold text-text-primary">{formatCurrency(cat.value)}</span>
                          <span className="text-[10px] text-text-muted">({pct}%)</span>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Transactions List */}
          <div>
            <div className="flex items-center justify-between mb-3 px-1">
              <h3 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">
                Ultimele Tranzacții
              </h3>
              <span className="text-xs text-text-muted">{transactions?.length ?? 0} înregistrări</span>
            </div>

            {txLoading ? (
              <Spinner className="py-12" />
            ) : !transactions?.length ? (
              <Card><p className="text-sm text-text-muted text-center py-8">Nu există tranzacții înregistrate.</p></Card>
            ) : (
              <div className="space-y-2">
                <AnimatePresence>
                  {transactions.map((txn: Transaction) => (
                    <motion.div
                      key={txn.id}
                      layout
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, height: 0 }}
                    >
                      <Card className="flex items-center gap-3 py-3 px-4 hover:border-border/80 transition-colors">
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                            txn.type === "income"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : "bg-rose-500/10 text-rose-400"
                          }`}
                        >
                          <Wallet className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-sm font-semibold tabular-nums ${
                                txn.type === "income" ? "text-emerald-400" : "text-rose-400"
                              }`}
                            >
                              {txn.type === "income" ? "+" : "-"}{formatCurrency(txn.amount)}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-md bg-surface text-text-secondary border border-border/50 capitalize">
                              {txn.category || "altele"}
                            </span>
                          </div>
                          {txn.description && (
                            <p className="text-xs text-text-muted truncate mt-0.5">{txn.description}</p>
                          )}
                        </div>
                        <span className="text-xs text-text-muted shrink-0">
                          {formatTransactionDate(txn.transaction_date || txn.tx_date)}
                        </span>
                        <button
                          onClick={() => deleteMut.mutate(txn.id)}
                          className="p-1.5 rounded-lg text-text-muted hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0"
                          title="Șterge tranzacția"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </Card>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>
          {selectedCategory && <div ref={categoryPanelRef}><Card className="p-4"><div className="mb-3 flex items-center justify-between"><div><h3 className="text-sm font-semibold text-text-primary">{selectedCategory}</h3><p className="text-xs text-text-muted">Înregistrări din luna curentă</p></div><button type="button" onClick={() => setSelectedCategory(null)} className="text-xs text-text-muted hover:text-text-primary">Închide</button></div>{categoryLoading ? <Spinner className="py-4" /> : categoryError ? <p className="rounded-xl bg-amber-500/10 p-3 text-xs text-amber-600">Nu am putut încărca detaliile. Repornește Lora pentru a activa endpointul nou.</p> : (categoryTransactions?.length ? categoryTransactions : fallbackCategoryTransactions).length ? <div className="space-y-2">{(categoryTransactions?.length ? categoryTransactions : fallbackCategoryTransactions).map((txn) => <div key={txn.id} className="flex items-center justify-between rounded-xl border border-border px-3 py-2 text-sm"><div className="min-w-0"><p className="truncate text-text-primary">{txn.description || "Cheltuială"}</p><p className="text-xs text-text-muted">{formatTransactionDate(txn.transaction_date || txn.tx_date)}</p></div><span className="ml-3 shrink-0 font-medium tabular-nums text-rose-400">-{formatCurrency(txn.amount)}</span></div>)}</div> : <p className="py-4 text-center text-xs text-text-muted">Nu există înregistrări pentru această categorie.</p>}</Card></div>}
          <div className="pt-2"><button type="button" onClick={() => setShowBudgets((value) => !value)} className="text-xs text-text-muted transition-colors hover:text-text-primary">{showBudgets ? "Ascunde bugetele" : "Bugete și alerte"}</button></div>
          {showBudgets && <Card className="p-4"><div className="grid w-full gap-2 sm:grid-cols-[minmax(120px,1fr)_110px_120px_auto]"><Input value={budgetCategory} onChange={(e) => setBudgetCategory(e.target.value)} placeholder="Categorie sau Total" /><Input type="number" min="1" value={budgetAmount} onChange={(e) => setBudgetAmount(e.target.value)} placeholder="RON" /><select value={budgetPeriod} onChange={(e) => setBudgetPeriod(e.target.value as "weekly" | "monthly")} className="rounded-xl border border-border bg-surface px-3 text-sm text-text-primary outline-none"><option value="weekly">Săptămânal</option><option value="monthly">Lunar</option></select><Button disabled={!budgetAmount || budgetMut.isPending} onClick={() => budgetMut.mutate({ category: budgetCategory.trim() || "Total", amount: Number(budgetAmount), period: budgetPeriod })}>Salvează</Button></div>{!!summary?.budgets?.length && <div className="mt-4 grid gap-2 sm:grid-cols-2">{summary.budgets.map((budget) => { const monthlyLimit = Number(budget.monthly_limit || 0); const weeklyLimit = Number(budget.weekly_limit || 0); const monthlyPct = monthlyLimit ? Math.min(100, Number(budget.monthly_spent || 0) / monthlyLimit * 100) : 0; const weeklyPct = weeklyLimit ? Math.min(100, Number(budget.weekly_spent || 0) / weeklyLimit * 100) : 0; return <div key={budget.category} className="rounded-xl border border-border p-3"><div className="flex items-center justify-between text-xs"><span className="font-medium text-text-primary">{budget.category}</span><span className="text-text-muted">{monthlyLimit ? `${formatCurrency(Number(budget.monthly_spent || 0))} / ${formatCurrency(monthlyLimit)}` : "Fără buget lunar"}</span></div>{monthlyLimit > 0 && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface"><div className={`h-full rounded-full ${monthlyPct >= 100 ? "bg-rose-500" : monthlyPct >= 80 ? "bg-amber-500" : "bg-primary"}`} style={{ width: `${monthlyPct}%` }} /></div>}{weeklyLimit > 0 && <p className="mt-2 text-[11px] text-text-muted">Săptămâna: {formatCurrency(Number(budget.weekly_spent || 0))} / {formatCurrency(weeklyLimit)} ({Math.round(weeklyPct)}%)</p>}</div> })}</div>}</Card>}
        </div>
      )}

      {/* Tab: RECEIPT & PRODUCT MEMORY */}
      {activeTab === "memory" && (
        <div className="space-y-6">
          {/* Info Card */}
          <div className="glass-strong rounded-2xl p-5 shadow-apple-heavy border border-primary/20">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-xl bg-primary/15 text-primary flex items-center justify-center shrink-0 mt-0.5">
                <Sparkles className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-text-primary mb-1">
                  Bază de Cunoștințe & Memorie Bonuri (OCR Local)
                </h3>
                <p className="text-xs text-text-secondary leading-relaxed">
                  Fiecare bon scanat cu Apple Vision OCR îmbunătățește această memorie.
                  Produsele și comercianții recunoscuți sunt auto-categorisiți instantaneu la viitoarele scanări.
                </p>
              </div>
            </div>
          </div>

          {/* Recognized Merchants Section */}
          <div className="glass-strong rounded-2xl p-5 shadow-apple-heavy">
            <div className="flex items-center gap-2 mb-3">
              <Store className="w-4 h-4 text-primary" />
              <h3 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">
                Comercianți & Magazine Recunoscute ({merchantMemories?.length ?? 0})
              </h3>
            </div>
            {merchLoading ? (
              <Spinner className="py-4" />
            ) : !merchantMemories?.length ? (
              <p className="text-xs text-text-muted py-2">Niciun comerciant învățat încă. Se vor salva automat la scanarea bonurilor.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {merchantMemories.map((m) => (
                  <div
                    key={m.id}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] border border-border/50 text-xs"
                  >
                    <Store className="w-3.5 h-3.5 text-text-muted" />
                    <span className="font-semibold text-text-primary">{m.clean_name}</span>
                    <span className="text-[10px] text-text-muted font-mono bg-surface px-1.5 py-0.5 rounded">
                      {m.raw_pattern}
                    </span>
                    <span className="text-[10px] text-primary font-bold">x{m.frequency}</span>
                    <button
                      onClick={() => deleteMerchMut.mutate(m.id)}
                      className="text-text-muted hover:text-rose-400 transition-colors ml-1"
                      title="Șterge magazin"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Learned Products Section */}
          <div className="space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-primary" />
                <h3 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-wider">
                  Produse Învățate ({filteredProducts.length})
                </h3>
              </div>
              <div className="relative w-full sm:w-64">
                <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Caută produs, magazin, categorie..."
                  className="pl-9 text-xs h-9"
                />
              </div>
            </div>

            {prodLoading ? (
              <Spinner className="py-12" />
            ) : !filteredProducts.length ? (
              <Card>
                <p className="text-sm text-text-muted text-center py-8">
                  {searchQuery ? "Niciun produs nu corespunde căutării." : "Nu există produse înregistrate în memoria bonurilor."}
                </p>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <AnimatePresence>
                  {filteredProducts.map((p) => (
                    <motion.div
                      key={p.id}
                      layout
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                    >
                      <Card className="p-4 hover:border-border/80 transition-colors space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-text-primary leading-tight">{p.clean_name}</p>
                            <p className="text-[11px] text-text-muted font-mono mt-0.5 truncate max-w-xs">
                              {p.raw_pattern}
                            </p>
                          </div>
                          <button
                            onClick={() => deleteProdMut.mutate(p.id)}
                            className="p-1.5 rounded-lg text-text-muted hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0"
                            title="Șterge din memorie"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-border/40 text-xs">
                          <span className="px-2 py-0.5 rounded-md bg-primary/10 text-primary font-medium text-[11px] capitalize">
                            {p.category}
                          </span>
                          {p.merchant && (
                            <span className="px-2 py-0.5 rounded-md bg-surface text-text-secondary text-[11px]">
                              {p.merchant}
                            </span>
                          )}
                          {p.last_price != null && (
                            <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 font-semibold tabular-nums text-[11px]">
                              {formatCurrency(p.last_price)}
                            </span>
                          )}
                          <span className="text-[10px] text-text-muted ml-auto">
                            detectat de {p.frequency}×
                          </span>
                        </div>
                      </Card>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Inline transaction form */}
      {showModal && <Card className="border-primary/30 p-4 max-w-2xl mx-auto max-h-[70vh] overflow-y-auto overscroll-contain">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold text-text-primary">Tranzacție nouă</h2><button type="button" onClick={() => setShowModal(false)} className="text-xs text-text-secondary">Anulează</button></div>
        <div className="space-y-3">
          <Input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Sumă (RON)"
            type="number"
            min="0"
            step="0.01"
            autoFocus
          />
          <Input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Categorie (ex. Alimente, Chirie, Utilități)"
          />
          <div className="flex gap-2">
            {(["expense", "income"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setType(t)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium capitalize transition-all ${
                  type === t
                    ? t === "income"
                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                      : "bg-rose-500/15 text-rose-400 border border-rose-500/20"
                    : "bg-surface text-text-secondary border border-border"
                }`}
              >
                {t === "expense" ? "Cheltuială" : "Venit"}
              </button>
            ))}
          </div>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Descriere (opțional)"
          />
          <Button
            className="w-full"
            disabled={!amount || parseFloat(amount) <= 0 || !category.trim() || createMut.isPending}
            onClick={handleSubmit}
          >
            {createMut.isPending ? <Spinner size="sm" /> : "Adaugă Tranzacție"}
          </Button>
        </div>
      </Card>}
    </motion.div>
  )
}
