import { useState } from "react"
import { Wallet, ShoppingCart, Luggage, CloudSun, MapPin, Newspaper } from "lucide-react"
import Finance from "./Finance"
import Shopping from "./Shopping"
import TravelPage from "./Travel"
import WeatherPage from "./Weather"
import Places from "./Places"
import News from "./News"

const tabs = [
  { key: "finance", label: "Finance", icon: Wallet },
  { key: "shopping", label: "Shopping", icon: ShoppingCart },
  { key: "outings", label: "Ieșiri", icon: Luggage },
  { key: "info", label: "Info", icon: CloudSun },
] as const

type TabKey = (typeof tabs)[number]["key"]

export default function Life() {
  const [active, setActive] = useState<TabKey>("finance")

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
          {active === "finance" && <Finance />}
          {active === "shopping" && <Shopping />}
          {active === "outings" && <div className="space-y-8"><TravelPage /><Places /></div>}
          {active === "info" && <div className="space-y-8"><WeatherPage /><News /></div>}
        </div>
      </div>
    </div>
  )
}
