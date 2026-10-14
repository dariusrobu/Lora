import { useState } from "react"
import { ModeSelector, PageHeader } from "../components/ui"
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
          <PageHeader eyebrow="Spatial OS · Wellness" title="Body" description="Sănătate, mișcare și energie într-o vedere simplă." action={<ModeSelector value={active} options={tabs.map((t) => ({ value: t.key, label: t.label }))} onChange={setActive} />} />
      {active === "health" && <Health />}
      {active === "workout" && <Workout />}
      {active === "nutrition" && <Nutrition />}
      {active === "mood" && <Mood />}
        </div>
      </div>
    </div>
  )
}
