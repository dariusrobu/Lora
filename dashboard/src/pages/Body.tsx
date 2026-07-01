import { useState } from "react"
import { Heart, Dumbbell, Apple, Smile } from "lucide-react"
import Health from "./Health"
import Workout from "./Workout"
import Nutrition from "./Nutrition"
import Mood from "./Mood"

const tabs = [
  { key: "health", label: "Health", icon: Heart },
  { key: "workout", label: "Workout", icon: Dumbbell },
  { key: "nutrition", label: "Nutrition", icon: Apple },
  { key: "mood", label: "Mood", icon: Smile },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Body() {
  const [active, setActive] = useState<TabKey>("health")

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div>
          <div className="flex gap-1 mb-6 overflow-x-auto pb-1">
        {tabs.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.key}
              onClick={() => setActive(t.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                active === t.key
                  ? "bg-surface text-text-primary border border-border"
                  : "text-text-secondary hover:text-text-primary border border-transparent"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          )
        })}
      </div>
      {active === "health" && <Health />}
      {active === "workout" && <Workout />}
      {active === "nutrition" && <Nutrition />}
      {active === "mood" && <Mood />}
        </div>
      </div>
    </div>
  )
}
