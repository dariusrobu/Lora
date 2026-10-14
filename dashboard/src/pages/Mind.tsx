import { useState } from "react"
import { ModeSelector, PageHeader } from "../components/ui"
import Notes from "./Notes"
import Reading from "./Reading"
import Memory from "./Memory"
import Insights from "./Insights"

const tabs = [
  { key: "notes", label: "Notes" },
  { key: "ideas", label: "Idei" },
  { key: "reading", label: "Lectură" },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Mind() {
  const [active, setActive] = useState<TabKey>("notes")

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div>
          <PageHeader eyebrow="Spatial OS · Inner life" title="Mind" description="Note, idei și lucrurile pe care vrei să le păstrezi." action={<ModeSelector value={active} options={tabs.map((t) => ({ value: t.key, label: t.label }))} onChange={setActive} />} />
      {active === "notes" && <Notes />}
      {active === "ideas" && <div className="space-y-8"><Memory /><Insights /></div>}
      {active === "reading" && <Reading />}
        </div>
      </div>
    </div>
  )
}
