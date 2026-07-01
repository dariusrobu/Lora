import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Sparkles, Lightbulb } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"

export default function Insights() {
  const { data, isLoading } = useQuery({
    queryKey: ["insights"],
    queryFn: () => fetch("/api/insights").then((r) => r.json()),
  })

  if (isLoading) return <Spinner className="py-12" />

  const items = Array.isArray(data) ? data : data?.insights ?? []

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Insights</h1>
        <p className="text-text-secondary text-sm">AI-generated observations</p>
      </div>
      <div className="space-y-2">
        {items.length === 0 ? (
          <Card><p className="text-sm text-text-muted text-center py-8">No insights yet</p></Card>
        ) : (
          items.map((item: Record<string, unknown>, i: number) => (
            <Card key={i} className="flex items-start gap-3 py-3 px-4">
              <Lightbulb className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
              <p className="text-sm">{String(item.text ?? item.insight ?? item.message ?? "")}</p>
            </Card>
          ))
        )}
      </div>
    </motion.div>
  )
}
