import { useState } from "react"
import { ChevronDown } from "lucide-react"
import Tasks from "./Tasks"
import Goals from "./Goals"
import Projects from "./Projects"
import CalendarPage from "./Calendar"
import FocusPage from "./Focus"

const tabs = [
  { key: "tasks", label: "Azi" },
  { key: "goals", label: "Obiective" },
  { key: "calendar", label: "Calendar" },
  { key: "more", label: "Mai mult" },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Plan() {
  const [active, setActive] = useState<TabKey>("tasks")

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div>
          <label className="relative mb-6 flex w-fit items-center gap-2 text-sm font-semibold text-text-primary">
            <span>Plan · {tabs.find((t) => t.key === active)?.label}</span><ChevronDown className="w-4 h-4 text-text-muted" />
            <select value={active} onChange={(e) => setActive(e.target.value as TabKey)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Alege secțiunea Plan">
              {tabs.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
          </label>
      {active === "tasks" && <Tasks />}
      {active === "goals" && <Goals />}
      {active === "calendar" && <CalendarPage />}
      {active === "more" && <div className="space-y-8"><Projects /><FocusPage /></div>}
        </div>
      </div>
    </div>
  )
}
