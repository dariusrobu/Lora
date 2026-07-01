import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Plus, DollarSign, CalendarDays, CheckCircle2 } from "lucide-react"
import { createTask } from "../api/queries/tasks"
import { createTransaction } from "../api/queries/finance"
import { createEvent } from "../api/queries/calendar"
import { useNotify } from "../context/NotificationContext"
import { BottomSheet } from "./ui/BottomSheet"

const expenseCategories = [
  "Food", "Transport", "Shopping", "Entertainment", "Bills", "Health", "Other",
]

const actions = [
  { id: "task", icon: Plus, label: "Task" },
  { id: "expense", icon: DollarSign, label: "Expense" },
  { id: "event", icon: CalendarDays, label: "Event" },
]

export function QuickActions() {
  const qc = useQueryClient()
  const { notify } = useNotify()
  const [modal, setModal] = useState<string | null>(null)

  const [taskTitle, setTaskTitle] = useState("")
  const [taskPriority, setTaskPriority] = useState<"high" | "medium" | "low">("medium")

  const [expAmount, setExpAmount] = useState("")
  const [expCategory, setExpCategory] = useState("Food")
  const [expDesc, setExpDesc] = useState("")

  const [evTitle, setEvTitle] = useState("")
  const [evDate, setEvDate] = useState(new Date().toISOString().slice(0, 10))
  const [evTime, setEvTime] = useState("")

  const createTaskMut = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      setTaskTitle("")
      setModal(null)
      notify("Task added", CheckCircle2)
    },
  })

  const createExpMut = useMutation({
    mutationFn: createTransaction,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance-history"] })
      qc.invalidateQueries({ queryKey: ["finance-summary"] })
      setExpAmount("")
      setExpCategory("Food")
      setExpDesc("")
      setModal(null)
      notify("Expense added", DollarSign)
    },
  })

  const createEventMut = useMutation({
    mutationFn: createEvent,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["calendar"] })
      setEvTitle("")
      setModal(null)
      notify("Event created", CalendarDays)
    },
  })

  return (
    <>
      <div className="flex items-center gap-2 flex-wrap">
        {actions.map(({ id, icon: Icon, label }, i) => (
          <motion.button
            key={id}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setModal(id)}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.04 }}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full glass-strong text-xs font-medium text-text-secondary hover:text-primary hover:bg-primary/10 transition-all"
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </motion.button>
        ))}
      </div>

      <BottomSheet open={modal === "task"} onClose={() => setModal(null)} title="Add Task">
        <div className="space-y-4">
          <input
            value={taskTitle}
            onChange={(e) => setTaskTitle(e.target.value)}
            placeholder="What needs to be done?"
            className="w-full bg-surface border border-border rounded-xl py-3 px-4 text-apple-body text-text-primary placeholder:text-text-muted outline-none focus:border-text-muted/30 transition-colors"
          />
          <div className="flex gap-2">
            {(["high", "medium", "low"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setTaskPriority(p)}
                className={`flex-1 py-2.5 rounded-lg text-apple-caption2 font-semibold uppercase tracking-wider transition-all ${
                  taskPriority === p
                    ? "bg-text-primary text-bg"
                    : "bg-surface text-text-muted border border-border"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          <button
            onClick={() => createTaskMut.mutate({ title: taskTitle, priority: taskPriority })}
            disabled={!taskTitle.trim() || createTaskMut.isPending}
            className="w-full py-3 rounded-xl bg-text-primary text-bg text-apple-body font-semibold disabled:opacity-40 transition-opacity"
          >
            {createTaskMut.isPending ? "Adding..." : "Add Task"}
          </button>
        </div>
      </BottomSheet>

      <BottomSheet open={modal === "expense"} onClose={() => setModal(null)} title="Add Expense">
        <div className="space-y-4">
          <input
            type="number"
            value={expAmount}
            onChange={(e) => setExpAmount(e.target.value)}
            placeholder="Amount (RON)"
            className="w-full bg-surface border border-border rounded-xl py-3 px-4 text-apple-body text-text-primary placeholder:text-text-muted outline-none focus:border-text-muted/30 transition-colors"
          />
          <select
            value={expCategory}
            onChange={(e) => setExpCategory(e.target.value)}
            className="w-full bg-surface border border-border rounded-xl py-3 px-4 text-apple-body text-text-primary outline-none focus:border-text-muted/30 transition-colors"
          >
            {expenseCategories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <input
            value={expDesc}
            onChange={(e) => setExpDesc(e.target.value)}
            placeholder="Description (optional)"
            className="w-full bg-surface border border-border rounded-xl py-3 px-4 text-apple-body text-text-primary placeholder:text-text-muted outline-none focus:border-text-muted/30 transition-colors"
          />
          <button
            onClick={() => createExpMut.mutate({ amount: Number(expAmount), category: expCategory, description: expDesc, type: "expense" })}
            disabled={!expAmount || Number(expAmount) <= 0 || createExpMut.isPending}
            className="w-full py-3 rounded-xl bg-text-primary text-bg text-apple-body font-semibold disabled:opacity-40 transition-opacity"
          >
            {createExpMut.isPending ? "Adding..." : "Add Expense"}
          </button>
        </div>
      </BottomSheet>

      <BottomSheet open={modal === "event"} onClose={() => setModal(null)} title="Add Event">
        <div className="space-y-4">
          <input
            value={evTitle}
            onChange={(e) => setEvTitle(e.target.value)}
            placeholder="Event title"
            className="w-full bg-surface border border-border rounded-xl py-3 px-4 text-apple-body text-text-primary placeholder:text-text-muted outline-none focus:border-text-muted/30 transition-colors"
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              type="date"
              value={evDate}
              onChange={(e) => setEvDate(e.target.value)}
              className="bg-surface border border-border rounded-xl py-3 px-4 text-apple-body text-text-primary outline-none focus:border-text-muted/30 transition-colors"
            />
            <input
              type="time"
              value={evTime}
              onChange={(e) => setEvTime(e.target.value)}
              className="bg-surface border border-border rounded-xl py-3 px-4 text-apple-body text-text-primary outline-none focus:border-text-muted/30 transition-colors"
            />
          </div>
          <button
            onClick={() => createEventMut.mutate({ title: evTitle, date: evDate, time: evTime || undefined })}
            disabled={!evTitle.trim() || createEventMut.isPending}
            className="w-full py-3 rounded-xl bg-text-primary text-bg text-apple-body font-semibold disabled:opacity-40 transition-opacity"
          >
            {createEventMut.isPending ? "Adding..." : "Add Event"}
          </button>
        </div>
      </BottomSheet>
    </>
  )
}
