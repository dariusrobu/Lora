import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Luggage, CheckCircle2, Circle } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"
import type { TravelList } from "../types"

export default function TravelPage() {
  const qc = useQueryClient()

  const { data, isLoading } = useQuery<TravelList>({
    queryKey: ["travel"],
    queryFn: () => fetch("/api/travel/lists").then((r) => r.json()),
  })

  const toggleMut = useMutation({
    mutationFn: async ({ id, is_packed }: { id: number; is_packed: boolean }) => {
      await fetch(`/api/travel/items/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_packed: !is_packed }),
      })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["travel"] }),
  })

  if (isLoading) return <Spinner className="py-12" />

  const lists = data ?? {}

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Travel</h1>
        <p className="text-text-secondary text-sm">Packing lists</p>
      </div>
      {Object.keys(lists).length === 0 ? (
        <Card><p className="text-sm text-text-muted text-center py-8">No packing lists</p></Card>
      ) : (
        <div className="space-y-4">
          {Object.entries(lists).map(([name, items]) => {
            const itemList = Array.isArray(items) ? items : []
            return <Card key={name}>
              <h3 className="text-sm font-semibold mb-2 capitalize">{name}</h3>
              <div className="space-y-1">
                {itemList.map((item: any) => (
                  <div key={item.id} className="flex items-center gap-2 text-sm">
                    <button onClick={() => toggleMut.mutate({ id: item.id, is_packed: item.is_packed })}>
                      {item.is_packed ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Circle className="w-4 h-4 text-text-muted" />
                      )}
                    </button>
                    <span className={item.is_packed ? "line-through text-text-muted" : ""}>
                      {item.item}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          })}
        </div>
      )}
    </motion.div>
  )
}
