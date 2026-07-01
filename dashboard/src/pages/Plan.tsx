import { useState } from "react"
import { CheckSquare, Target, FolderKanban, CalendarDays, Timer } from "lucide-react"
import Tasks from "./Tasks"
import Goals from "./Goals"
import Projects from "./Projects"
import CalendarPage from "./Calendar"
import FocusPage from "./Focus"

const tabs = [
  { key: "tasks", label: "Tasks", icon: CheckSquare },
  { key: "goals", label: "Goals", icon: Target },
  { key: "projects", label: "Projects", icon: FolderKanban },
  { key: "calendar", label: "Calendar", icon: CalendarDays },
  { key: "focus", label: "Focus", icon: Timer },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Plan() {
  const [active, setActive] = useState<TabKey>("tasks")

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
      {active === "tasks" && <Tasks />}
      {active === "goals" && <Goals />}
      {active === "projects" && <Projects />}
      {active === "calendar" && <CalendarPage />}
      {active === "focus" && <FocusPage />}
        </div>
      </div>
    </div>
  )
}
