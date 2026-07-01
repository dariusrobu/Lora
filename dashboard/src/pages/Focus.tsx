import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Timer, Play, Square } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Button } from "../components/ui/Button"
import { Spinner } from "../components/ui/Spinner"

export default function FocusPage() {
  const qc = useQueryClient()
  const [elapsed, setElapsed] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ["focus"],
    queryFn: () => fetch("/api/focus/status").then((r) => r.json()),
    refetchInterval: 30000,
  })

  const startMut = useMutation({
    mutationFn: async () => {
      await fetch("/api/focus/start", { method: "POST" })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["focus"] }),
  })

  const isActive = data?.active ?? false
  const startedAt = data?.started_at ? new Date(data.started_at) : null

  useEffect(() => {
    if (!isActive || !startedAt) return
    const update = () => setElapsed(Math.floor((Date.now() - startedAt.getTime()) / 1000))
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [isActive, startedAt])

  const hours = Math.floor(elapsed / 3600)
  const minutes = Math.floor((elapsed % 3600) / 60)
  const seconds = elapsed % 60
  const timeStr = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`

  if (isLoading) return <Spinner className="py-12" />

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Focus</h1>
        <p className="text-text-secondary text-sm">Concentration timer</p>
      </div>
      <Card className="text-center py-10">
        <Timer className="w-10 h-10 text-primary mx-auto mb-4" />
        <p className="text-5xl font-mono font-bold mb-6 tracking-wider">{timeStr}</p>
        <Button
          onClick={() => startMut.mutate()}
          disabled={startMut.isPending}
          variant={isActive ? "danger" : "primary"}
        >
          {isActive ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          {isActive ? "Stop" : "Start Focus"}
        </Button>
      </Card>
    </motion.div>
  )
}
