import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"

function getWeatherEmoji(condition?: string) {
  const c = (condition ?? "").toLowerCase()
  if (c.includes("rain") || c.includes("ploaie")) return "🌧"
  if (c.includes("cloud") || c.includes("nor")) return "☁️"
  if (c.includes("snow") || c.includes("zăpadă")) return "❄️"
  if (c.includes("thunder") || c.includes("furtună")) return "⛈"
  if (c.includes("fog") || c.includes("ceață")) return "🌫"
  if (c.includes("clear") || c.includes("senin")) return "☀️"
  return "🌤"
}

const MOCK = { temp: 22, feels_like: 20, temp_min: 16, temp_max: 26, condition: "Parțial noros", humidity: 65 }

export default function WeatherWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ["kiosk-weather"],
    queryFn: () => fetch("/api/weather?lat=44.43&lon=26.10").then((r) => r.json()),
    refetchInterval: 60_000,
    retry: 1,
  })

  if (isLoading && !data) return <Loader2 className="w-6 h-6 animate-spin text-blue-400 mx-auto mt-6" />

  const w = data?.current ?? MOCK

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <span className="text-5xl leading-none">{getWeatherEmoji(w.condition)}</span>
      <div className="text-6xl font-light leading-none mt-1">
        {Math.round(w.temp ?? w.temperature ?? 0)}°
      </div>
      <div className="text-sm opacity-60 mt-1">{w.condition ?? ""}</div>
      <div className="text-xs opacity-40 mt-1">
        H:{Math.round(w.temp_max ?? 0)}° L:{Math.round(w.temp_min ?? 0)}°
      </div>
    </div>
  )
}
