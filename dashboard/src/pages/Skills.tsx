import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Zap, Plus, Flame } from "lucide-react"
import { Card, Button, Input, Badge, Modal, Spinner } from "../components/ui"
import type { Skill } from "../types"
import { fetchSkills, logSkill } from "../api/queries/skills"

export default function Skills() {
  const [modalOpen, setModalOpen] = useState(false)
  const [name, setName] = useState("")
  const queryClient = useQueryClient()

  const { data: skills, isLoading } = useQuery<Skill[]>({
    queryKey: ["skills"],
    queryFn: fetchSkills,
  })

  const logMutation = useMutation({
    mutationFn: logSkill,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] })
      setModalOpen(false)
      setName("")
    },
  })

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="h-6 w-6 text-yellow-500" />
          <h1 className="text-2xl font-bold">Skills</h1>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> New Skill
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {skills?.map((skill) => (
          <motion.div
            key={skill.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold">{skill.name}</h3>
                  <Badge variant="secondary">Lv.{skill.level}</Badge>
                </div>
                {skill.streak > 0 && (
                  <div className="flex items-center gap-1 text-orange-500">
                    <Flame className="h-4 w-4" />
                    <span className="text-sm font-medium">{skill.streak}</span>
                  </div>
                )}
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-sm text-text-secondary">
                  <span>XP</span>
                  <span>{skill.xp ?? 0} / {(skill.level ?? 1) * 100}</span>
                </div>
                <div className="h-1 bg-surface rounded-full overflow-hidden">
                  <div
                    className="h-full bg-yellow-500 rounded-full transition-all"
                    style={{
                      width: `${Math.min(100, ((skill.xp ?? 0) / ((skill.level ?? 1) * 100)) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}>
        <div className="space-y-4 p-4">
          <h2 className="text-lg font-semibold">New Skill</h2>
          <Input
            autoFocus
            placeholder="Skill name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Button
            onClick={() => logMutation.mutate({ name: name.trim() })}
            disabled={!name.trim() || logMutation.isPending}
          >
            Create
          </Button>
        </div>
      </Modal>
    </div>
  )
}
