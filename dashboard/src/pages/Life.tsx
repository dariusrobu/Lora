import { useState } from "react"
import { ChevronDown } from "lucide-react"
import Finance from "./Finance"
import Shopping from "./Shopping"
import TravelPage from "./Travel"
import WeatherPage from "./Weather"
import Places from "./Places"
import News from "./News"

const tabs = [
  { key: "finance", label: "Finance" },
  { key: "shopping", label: "Shopping" },
  { key: "outings", label: "Ieșiri" },
  { key: "info", label: "Info" },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Life() {
  const [active, setActive] = useState<TabKey>("finance")

  return (
    <div className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div>
          <label className="relative mb-6 flex w-fit items-center gap-2 text-sm font-semibold text-text-primary"><span>Life · {tabs.find((t) => t.key === active)?.label}</span><ChevronDown className="w-4 h-4 text-text-muted" /><select value={active} onChange={(e) => setActive(e.target.value as TabKey)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Alege secțiunea Life">{tabs.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}</select></label>
          {active === "finance" && <Finance />}
          {active === "shopping" && <Shopping />}
          {active === "outings" && <div className="space-y-8"><TravelPage /><Places /></div>}
          {active === "info" && <div className="space-y-8"><WeatherPage /><News /></div>}
        </div>
      </div>
    </div>
  )
}
