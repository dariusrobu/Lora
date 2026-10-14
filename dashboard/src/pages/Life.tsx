import { useState } from "react"
import { ModeSelector, PageHeader } from "../components/ui"
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
          <PageHeader eyebrow="Spatial OS · Life" title="Life" description="Bani, cumpărături, ieșiri și informații utile." action={<ModeSelector value={active} options={tabs.map((t) => ({ value: t.key, label: t.label }))} onChange={setActive} />} />
          {active === "finance" && <Finance />}
          {active === "shopping" && <Shopping />}
          {active === "outings" && <div className="space-y-8"><TravelPage /><Places /></div>}
          {active === "info" && <div className="space-y-8"><WeatherPage /><News /></div>}
        </div>
      </div>
    </div>
  )
}
