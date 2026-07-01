export interface WeatherCurrent {
  temp: number
  feels_like: number
  temp_min: number
  temp_max: number
  humidity: number
  pressure: number
  visibility: number
  wind_speed: number
  wind_deg: number
  condition: string
  icon: string
  city: string
  country: string
  sunrise: number
  sunset: number
}

export interface WeatherForecastDay {
  date: string
  temp_min: number
  temp_max: number
  condition: string
  icon: string
  humidity: number
  wind_speed: number
}

export interface WeatherResponse {
  current: WeatherCurrent
  forecast: WeatherForecastDay[]
}

export async function fetchWeather(lat: number, lon: number): Promise<WeatherResponse> {
  const res = await fetch(`/api/weather?lat=${lat}&lon=${lon}`)
  if (!res.ok) throw new Error("Failed to fetch weather")
  return res.json()
}
