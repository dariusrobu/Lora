import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { CloudSun, Thermometer, Droplets, Wind } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"

export default function WeatherPage() {
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null)

  useEffect(() => {
    navigator.geolocation.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => {},
    )
  }, [])

  const { data, isLoading } = useQuery({
    queryKey: ["weather", coords],
    queryFn: () => {
      if (!coords) return Promise.reject("No location")
      return fetch(`/api/weather?lat=${coords.lat}&lon=${coords.lon}`).then((r) => r.json())
    },
    refetchInterval: 600_000,
    enabled: !!coords,
  })

  if (isLoading) return <Spinner className="py-12" />

  const w = data?.current
  const forecast = data?.forecast ?? []

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Weather</h1>
        {w && <p className="text-text-secondary text-sm">{w.city ?? w.name}</p>}
      </div>

      {w && (
        <Card className="mb-4">
          <div className="flex items-center gap-4">
            <CloudSun className="w-12 h-12 text-primary" />
            <div>
              <p className="text-4xl font-bold">{Math.round(w.temp ?? w.temperature ?? 0)}°</p>
              <p className="text-sm text-text-secondary capitalize">{w.condition ?? w.description ?? w.weather}</p>
            </div>
            <div className="ml-auto space-y-1 text-sm text-text-secondary">
              <p className="flex items-center gap-1"><Thermometer className="w-3 h-3" /> {w.feels_like ?? "-"}°</p>
              {w.humidity != null && <p className="flex items-center gap-1"><Droplets className="w-3 h-3" /> {w.humidity}%</p>}
              {w.wind_speed != null && <p className="flex items-center gap-1"><Wind className="w-3 h-3" /> {w.wind_speed} m/s</p>}
            </div>
          </div>
        </Card>
      )}

      {forecast.length > 0 && (
        <div className="grid grid-cols-5 gap-2">
          {forecast.slice(0, 5).map((day: any, i: number) => (
            <Card key={i} className="text-center py-3 px-2">
              <p className="text-xs text-text-secondary mb-1">{day.day ?? day.date ?? `Day ${i + 1}`}</p>
              <CloudSun className="w-5 h-5 mx-auto mb-1 text-primary" />
              <p className="text-sm font-semibold">{Math.round(day.temp ?? day.temperature ?? 0)}°</p>
            </Card>
          ))}
        </div>
      )}

      {!w && forecast.length === 0 && (
        <Card><p className="text-sm text-text-muted text-center py-8">No weather data</p></Card>
      )}
    </motion.div>
  )
}
