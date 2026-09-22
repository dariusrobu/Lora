import { useState } from "react"
import { ChevronDown } from "lucide-react"
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
          <label className="relative mb-6 flex w-fit items-center gap-2 text-sm font-semibold text-text-primary"><span>Mind · {tabs.find((t) => t.key === active)?.label}</span><ChevronDown className="w-4 h-4 text-text-muted" /><select value={active} onChange={(e) => setActive(e.target.value as TabKey)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Alege secțiunea Mind">{tabs.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}</select></label>
      {active === "notes" && <Notes />}
      {active === "ideas" && <div className="space-y-8"><Memory /><Insights /></div>}
      {active === "reading" && <Reading />}
        </div>
      </div>
    </div>
  )
}
