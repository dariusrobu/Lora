import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Droplets, Moon, Heart, Brain } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { Modal } from "../ui/Modal"
import { Button } from "../ui/Button"
import { api } from "../../api/client"

type Action = "task" | "mood" | "water" | "sleep" | "health"

const actions: { key: Action; label: string; icon: typeof Plus }[] = [
  { key: "task", label: "Task", icon: Plus },
  { key: "mood", label: "Mood", icon: Brain },
  { key: "water", label: "Apă", icon: Droplets },
  { key: "sleep", label: "Somn", icon: Moon },
  { key: "health", label: "Sănătate", icon: Heart },
]

export default function QuickActions() {
  const [open, setOpen] = useState<Action | null>(null)
  const qc = useQueryClient()

  const taskMut = useMutation({
    mutationFn: (title: string) => api.post("/api/tasks", { title }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["kiosk-tasks"] }); setOpen(null) },
  })
  const moodMut = useMutation({
    mutationFn: (mood: string) => api.post("/api/mood", { mood }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["kiosk-mood"] }); setOpen(null) },
  })
  const healthMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.post("/api/health", data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["kiosk-health"] }); setOpen(null) },
  })

  return (
    <>
      <div className="flex justify-center gap-5">
        {actions.map((a, i) => {
          const Icon = a.icon
          return (
            <motion.button
              key={a.key}
              onClick={() => setOpen(a.key)}
              className="flex flex-col items-center gap-1.5 text-text-secondary hover:text-purple-400 active:scale-90 transition-all py-1"
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.9 }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 + i * 0.04 }}
            >
              <Icon className="w-6 h-6" />
              <span className="text-sm font-medium">{a.label}</span>
            </motion.button>
          )
        })}
      </div>

      <AnimatePresence>
        {open === "task" && (
          <Modal open onClose={() => setOpen(null)} title="New Task">
            <TaskForm onSubmit={(v) => taskMut.mutate(v)} loading={taskMut.isPending} />
          </Modal>
        )}
        {open === "mood" && (
          <Modal open onClose={() => setOpen(null)} title="Log Mood">
            <MoodForm onSubmit={(v) => moodMut.mutate(v)} loading={moodMut.isPending} />
          </Modal>
        )}
        {open === "water" && (
          <Modal open onClose={() => setOpen(null)} title="Apă">
            <WaterForm onSubmit={(v) => healthMut.mutate(v)} loading={healthMut.isPending} />
          </Modal>
        )}
        {open === "sleep" && (
          <Modal open onClose={() => setOpen(null)} title="Somn">
            <SleepForm onSubmit={(v) => healthMut.mutate(v)} loading={healthMut.isPending} />
          </Modal>
        )}
        {open === "health" && (
          <Modal open onClose={() => setOpen(null)} title="Sănătate">
            <HealthForm onSubmit={(v) => healthMut.mutate(v)} loading={healthMut.isPending} />
          </Modal>
        )}
      </AnimatePresence>
    </>
  )
}

function TaskForm({ onSubmit, loading }: { onSubmit: (v: string) => void; loading: boolean }) {
  const [val, setVal] = useState("")
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (val.trim()) onSubmit(val.trim()) }}>
      <input
        autoFocus
        className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-primary mb-4"
        placeholder="What needs to be done?"
        value={val}
        onChange={(e) => setVal(e.target.value)}
      />
      <Button type="submit" className="w-full" disabled={!val.trim() || loading}>
        {loading ? "Saving..." : "Add Task"}
      </Button>
    </form>
  )
}

const moods = ["great", "good", "okay", "meh", "bad"]
const moodEmoji: Record<string, string> = { great: "😄", good: "🙂", okay: "😐", meh: "😕", bad: "😢" }

function MoodForm({ onSubmit, loading }: { onSubmit: (v: string) => void; loading: boolean }) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {moods.map((m) => (
        <button
          key={m}
          onClick={() => onSubmit(m)}
          disabled={loading}
          className="flex flex-col items-center gap-1 p-3 rounded-xl bg-surface hover:bg-[var(--color-surface)] border border-border transition-colors disabled:opacity-40"
        >
          <span className="text-2xl">{moodEmoji[m]}</span>
          <span className="text-[10px] text-text-secondary capitalize">{m}</span>
        </button>
      ))}
    </div>
  )
}

function WaterForm({ onSubmit, loading }: { onSubmit: (v: Record<string, unknown>) => void; loading: boolean }) {
  const [ml, setMl] = useState("200")
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit({ water_ml: parseInt(ml) }) }}>
      <p className="text-sm text-text-secondary mb-3">How much water did you drink?</p>
      <div className="flex gap-2 mb-4">
        {[200, 300, 500].map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setMl(String(v))}
            className={`flex-1 py-3 rounded-xl border text-sm font-medium transition-colors ${
              ml === String(v) ? "border-purple-400 bg-purple-400/10 text-purple-400" : "border-border bg-surface text-text-secondary"
            }`}
          >
            {v}ml
          </button>
        ))}
      </div>
      <Button type="submit" className="w-full" disabled={loading}>Log Water</Button>
    </form>
  )
}

function SleepForm({ onSubmit, loading }: { onSubmit: (v: Record<string, unknown>) => void; loading: boolean }) {
  const [hours, setHours] = useState("7")
  const [quality, setQuality] = useState("good")
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit({ sleep_hours: parseFloat(hours), sleep_quality: quality }) }}>
      <p className="text-sm text-text-secondary mb-3">Hours of sleep?</p>
      <input
        type="number"
        step="0.5"
        min="0"
        max="24"
        autoFocus
        className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-purple-400 mb-3"
        value={hours}
        onChange={(e) => setHours(e.target.value)}
      />
      <p className="text-sm text-text-secondary mb-2">Quality?</p>
      <div className="flex gap-2 mb-4">
        {["poor", "fair", "good", "great"].map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => setQuality(q)}
            className={`flex-1 py-2 rounded-xl border text-xs font-medium transition-colors ${
              quality === q ? "border-purple-400 bg-purple-400/10 text-purple-400" : "border-border bg-surface text-text-secondary"
            }`}
          >
            {q}
          </button>
        ))}
      </div>
      <Button type="submit" className="w-full" disabled={loading}>Log Sleep</Button>
    </form>
  )
}

function HealthForm({ onSubmit, loading }: { onSubmit: (v: Record<string, unknown>) => void; loading: boolean }) {
  const [weight, setWeight] = useState("")
  const [notes, setNotes] = useState("")
  return (
    <form onSubmit={(e) => {
      e.preventDefault()
      const data: Record<string, unknown> = {}
      if (weight) data.weight_kg = parseFloat(weight)
      if (notes.trim()) data.notes = notes.trim()
      onSubmit(data)
    }}>
      <p className="text-sm text-text-secondary mb-3">Log health data</p>
      <input
        type="number"
        step="0.1"
        placeholder="Weight (kg) — optional"
        autoFocus
        className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-purple-400 mb-3"
        value={weight}
        onChange={(e) => setWeight(e.target.value)}
      />
      <textarea
        placeholder="Notes — optional"
        className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-purple-400 mb-4 resize-none"
        rows={2}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      <Button type="submit" className="w-full" disabled={loading}>Log Health</Button>
    </form>
  )
}
