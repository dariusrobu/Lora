import { useState } from "react"
import Tasks from "./Tasks"
import Goals from "./Goals"
import Projects from "./Projects"
import CalendarPage from "./Calendar"
import FocusPage from "./Focus"
import { PageHeader, ModeSelector } from "../components/ui"

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
          <PageHeader eyebrow="Spatial OS" title="Plan" description="Organizează ce urmează, fără zgomot." action={<ModeSelector value={active} options={tabs.map((t) => ({ value: t.key, label: t.label }))} onChange={setActive} />} />
      {active === "tasks" && <Tasks />}
      {active === "goals" && <Goals />}
      {active === "calendar" && <CalendarPage />}
      {active === "more" && <div className="space-y-8"><Projects /><FocusPage /></div>}
        </div>
      </div>
    </div>
  )
}
