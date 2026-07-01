import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { MapPin, Plus, Trash2 } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { Modal } from "../components/ui/Modal"
import { Spinner } from "../components/ui/Spinner"

export default function Places() {
  const [showModal, setShowModal] = useState(false)
  const [name, setName] = useState("")
  const [address, setAddress] = useState("")
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["places"],
    queryFn: () => fetch("/api/places").then((r) => r.json()),
  })

  const saveMut = useMutation({
    mutationFn: async () => {
      await fetch("/api/places", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, address }),
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["places"] })
      setShowModal(false)
      setName("")
      setAddress("")
    },
  })

  if (isLoading) return <Spinner className="py-12" />

  const places = Array.isArray(data) ? data : data?.places ?? []

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Places</h1>
          <p className="text-text-secondary text-sm">Saved locations</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus className="w-4 h-4" /> Add
        </Button>
      </div>

      <div className="grid gap-3">
        {places.length === 0 ? (
          <Card><p className="text-sm text-text-muted text-center py-8">No saved places</p></Card>
        ) : (
          places.map((place: any) => (
            <Card key={place.id} className="flex items-center gap-3 py-3 px-4">
              <MapPin className="w-5 h-5 text-primary shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{place.name}</p>
                {place.address && <p className="text-xs text-text-secondary truncate">{place.address}</p>}
              </div>
            </Card>
          ))
        )}
      </div>

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Save Place">
        <div className="space-y-3">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Place name" autoFocus />
          <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Address" />
          <Button className="w-full" disabled={!name.trim() || saveMut.isPending} onClick={() => saveMut.mutate()}>
            Save
          </Button>
        </div>
      </Modal>
    </motion.div>
  )
}
