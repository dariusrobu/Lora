import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { fetchFinanceSummary, fetchFinanceHistory, createTransaction, deleteTransaction } from "../api/queries/finance"
import { Card } from "../components/ui/Card"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { Modal } from "../components/ui/Modal"
import { Spinner } from "../components/ui/Spinner"
import { Wallet, Plus, Trash2, TrendingUp, TrendingDown, DollarSign } from "lucide-react"
import type { Transaction } from "../types"

function formatCurrency(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n)
}

export default function Finance() {
  const [showModal, setShowModal] = useState(false)
  const [amount, setAmount] = useState("")
  const [category, setCategory] = useState("")
  const [type, setType] = useState<"income" | "expense">("expense")
  const [description, setDescription] = useState("")
  const qc = useQueryClient()

  const { data: summary } = useQuery({
    queryKey: ["finance", "summary"],
    queryFn: fetchFinanceSummary,
  })

  const { data: transactions, isLoading } = useQuery({
    queryKey: ["finance", "history"],
    queryFn: fetchFinanceHistory,
  })

  const deleteMut = useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] })
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

  const handleSubmit = () => {
    const parsed = parseFloat(amount)
    if (!isNaN(parsed) && parsed > 0) {
      createMut.mutate({ amount: parsed, category, type, description })
    }
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Finance</h1>
          <p className="text-text-secondary text-sm">Track your income and expenses</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus className="w-4 h-4" /> Transaction
        </Button>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="py-4 px-5">
          <div className="flex items-center gap-2 text-emerald-400 mb-1">
            <TrendingUp className="w-4 h-4" />
            <span className="text-xs font-medium uppercase tracking-wider">Income</span>
          </div>
          <p className="text-lg font-bold">{summary ? formatCurrency(summary.summary?.income) : "—"}</p>
        </Card>
        <Card className="py-4 px-5">
          <div className="flex items-center gap-2 text-red-400 mb-1">
            <TrendingDown className="w-4 h-4" />
            <span className="text-xs font-medium uppercase tracking-wider">Expenses</span>
          </div>
          <p className="text-lg font-bold">{summary ? formatCurrency(summary.summary?.expense) : "—"}</p>
        </Card>
        <Card className="py-4 px-5">
          <div className="flex items-center gap-2 text-primary mb-1">
            <DollarSign className="w-4 h-4" />
            <span className="text-xs font-medium uppercase tracking-wider">Balance</span>
          </div>
          <p className="text-lg font-bold">{summary ? formatCurrency(summary.summary?.balance) : "—"}</p>
        </Card>
      </div>

      {isLoading ? (
        <Spinner className="py-12" />
      ) : !transactions?.length ? (
        <Card><p className="text-sm text-text-muted text-center py-8">No transactions yet</p></Card>
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
                <Card className="flex items-center gap-3 py-3 px-4">
                  <Wallet className="w-5 h-5 text-text-muted shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${txn.type === "income" ? "text-emerald-400" : "text-red-400"}`}>
                        {txn.type === "income" ? "+" : "-"}{formatCurrency(txn.amount)}
                      </span>
                      <span className="text-xs text-text-secondary">{txn.category}</span>
                    </div>
                    {txn.description && (
                      <p className="text-xs text-text-muted truncate">{txn.description}</p>
                    )}
                  </div>
                  <span className="text-xs text-text-muted shrink-0">
                    {new Date(txn.transaction_date + "T00:00:00").toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => deleteMut.mutate(txn.id)}
                    className="text-text-muted hover:text-red-400 transition-colors shrink-0"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="New Transaction">
        <div className="space-y-3">
          <Input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Amount"
            type="number"
            min="0"
            step="0.01"
            autoFocus
          />
          <Input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Category (e.g. Food, Rent)"
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
                      : "bg-red-500/15 text-red-400 border border-red-500/20"
                    : "bg-surface text-text-secondary border border-border"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
          />
          <Button
            className="w-full"
            disabled={!amount || parseFloat(amount) <= 0 || !category.trim() || createMut.isPending}
            onClick={handleSubmit}
          >
            {createMut.isPending ? <Spinner size="sm" /> : "Add Transaction"}
          </Button>
        </div>
      </Modal>
    </motion.div>
  )
}
