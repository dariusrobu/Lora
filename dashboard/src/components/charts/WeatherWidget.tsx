import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { CloudSun, Droplets, Wind, Thermometer, ArrowRight, Maximize2 } from "lucide-react"
import { fetchWeather } from "../../api/queries/weather"
import { Card } from "../ui/Card"
import { Spinner } from "../ui/Spinner"

interface Props {
  onExpand?: () => void
}

function weatherEmoji(icon: string): string {
  if (!icon) return "🌤"
  const map: Record<string, string> = {
    "01d": "☀️", "01n": "🌙",
    "02d": "⛅", "02n": "☁️",
    "03d": "☁️", "03n": "☁️",
    "04d": "☁️", "04n": "☁️",
    "09d": "🌧", "09n": "🌧",
    "10d": "🌦", "10n": "🌧",
    "11d": "⛈", "11n": "⛈",
    "13d": "🌨", "13n": "🌨",
    "50d": "🌫", "50n": "🌫",
  }
  return map[icon] ?? "🌤"
}

function dayLabel(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00")
  const today = new Date()
  today.setHours(12, 0, 0, 0)
  const diff = Math.round((d.getTime() - today.getTime()) / 86400000)
  if (diff === 0) return "Today"
  if (diff === 1) return "Tomorrow"
  return d.toLocaleDateString("en-US", { weekday: "short" })
}

export function WeatherWidget({ onExpand }: Props) {
  const [coords] = useState<{ lat: number; lon: number }>({ lat: 45.9567, lon: 23.5664 })
  // Sebeș, Romania

  const { data, isLoading } = useQuery({
    queryKey: ["weather", coords?.lat, coords?.lon],
    queryFn: () => fetchWeather(coords!.lat, coords!.lon),
    enabled: !!coords,
    refetchInterval: 300_000,
  })

  const w = data?.current
  const forecast = data?.forecast ?? []

  return (
    <Card liquid hover>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-widest">Weather</h3>
        <div className="flex items-center gap-1">
          {onExpand && (
            <motion.button
              onClick={onExpand}
              whileTap={{ scale: 0.9 }}
              className="p-1.5 rounded-full text-text-muted hover:text-text-primary hover:bg-white/10 dark:hover:bg-white/[0.08] transition-colors"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </motion.button>
          )}
          <Link to="/life?tab=weather" className="p-1.5 rounded-full text-text-muted hover:text-text-primary hover:bg-white/10 dark:hover:bg-white/[0.08] transition-colors">
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
      {isLoading ? (
        <Spinner className="py-6" />
      ) : w ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="flex items-center gap-4 mb-3">
            <span className="text-4xl">{weatherEmoji(w.icon)}</span>
            <div>
              <span className="text-3xl font-bold text-text-primary">{Math.round(w.temp)}°</span>
              <p className="text-apple-caption1 text-text-muted capitalize">{w.condition}</p>
            </div>
            <div className="ml-auto space-y-0.5 text-apple-caption2 text-text-muted text-right">
              <p className="flex items-center gap-1 justify-end"><Thermometer className="w-3 h-3" /> {Math.round(w.feels_like)}°</p>
              <p className="flex items-center gap-1 justify-end"><Droplets className="w-3 h-3" /> {w.humidity}%</p>
              <p className="flex items-center gap-1 justify-end"><Wind className="w-3 h-3" /> {w.wind_speed?.toFixed(1)} m/s</p>
            </div>
          </div>
          {forecast.length > 0 && (
            <div className="flex gap-2">
              {forecast.slice(0, 5).map((day) => (
                <div key={day.date} className="flex-1 flex flex-col items-center gap-0.5 py-1.5 rounded-xl bg-white/40 dark:bg-white/[0.04]">
                  <span className="text-[10px] text-text-muted font-medium">{dayLabel(day.date)}</span>
                  <span className="text-base">{weatherEmoji(day.icon)}</span>
                  <span className="text-[11px] font-semibold text-text-primary tabular-nums">
                    {Math.round(day.temp_max)}°
                  </span>
                  <span className="text-[9px] text-text-muted tabular-nums">
                    {Math.round(day.temp_min)}°
                  </span>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      ) : (
        <div className="flex flex-col items-center py-4 text-center">
          <CloudSun className="w-8 h-8 text-text-muted mb-2" />
          <p className="text-apple-caption1 text-text-muted">No weather data</p>
        </div>
      )}
    </Card>
  )
}
