import { useState } from "react"
import { StickyNote, BookOpen, Brain, Sparkles } from "lucide-react"
import Notes from "./Notes"
import Reading from "./Reading"
import Memory from "./Memory"
import Insights from "./Insights"

const tabs = [
  { key: "notes", label: "Notes", icon: StickyNote },
  { key: "reading", label: "Reading", icon: BookOpen },
  { key: "memory", label: "Memory", icon: Brain },
  { key: "insights", label: "Insights", icon: Sparkles },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Mind() {
  const [active, setActive] = useState<TabKey>("notes")

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
                  ? "bg-primary/15 text-primary border border-primary/20"
                  : "text-text-secondary hover:text-text-primary border border-transparent"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          )
        })}
      </div>
      {active === "notes" && <Notes />}
      {active === "reading" && <Reading />}
      {active === "memory" && <Memory />}
      {active === "insights" && <Insights />}
        </div>
      </div>
    </div>
  )
}
