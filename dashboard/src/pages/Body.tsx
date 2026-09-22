import { useState } from "react"
import { ChevronDown } from "lucide-react"
import Health from "./Health"
import Workout from "./Workout"
import Nutrition from "./Nutrition"
import Mood from "./Mood"

const tabs = [
  { key: "health", label: "Health" },
  { key: "workout", label: "Workout" },
  { key: "nutrition", label: "Nutrition" },
  { key: "mood", label: "Mood" },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Body() {
  const [active, setActive] = useState<TabKey>("health")

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div>
          <label className="relative mb-6 flex w-fit items-center gap-2 text-sm font-semibold text-text-primary"><span>Body · {tabs.find((t) => t.key === active)?.label}</span><ChevronDown className="w-4 h-4 text-text-muted" /><select value={active} onChange={(e) => setActive(e.target.value as TabKey)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Alege secțiunea Body">{tabs.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}</select></label>
      {active === "health" && <Health />}
      {active === "workout" && <Workout />}
      {active === "nutrition" && <Nutrition />}
      {active === "mood" && <Mood />}
        </div>
      </div>
    </div>
  )
}
