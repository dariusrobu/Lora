import axios from "axios"

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ""

export const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
    "Bypass-Tunnel-Reminder": "true",
  },
  timeout: 15000,
})

// A Mini App launch supplies fresh, signed initData. Never persist or replay it.
let telegramInitData = ""
let telegramAuthPromise: Promise<string | null> | null = null

async function authenticateTelegram(): Promise<string | null> {
  if (!telegramInitData) return null
  if (telegramAuthPromise) return telegramAuthPromise
  telegramAuthPromise = axios.post(`${BASE_URL}/api/auth/telegram`, { init_data: telegramInitData }, {
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
      "Bypass-Tunnel-Reminder": "true",
    },
  }).then((res) => {
    const token = res.data?.access_token as string | undefined
    if (token) localStorage.setItem("lora_token", token)
    return token ?? null
  }).catch((err) => {
    console.warn("[TMA] Telegram auto-login failed:", err)
    return null
  }).finally(() => {
    telegramAuthPromise = null
  })
  return telegramAuthPromise
}

if (typeof window !== "undefined") {
  localStorage.removeItem("lora_telegram_init_data")
  const tg = (window as unknown as { Telegram?: { WebApp?: { ready?: () => void; expand?: () => void; initData?: string } } }).Telegram?.WebApp
  if (tg) {
    try {
      tg.ready?.()
      tg.expand?.()
      if (tg.initData) {
        telegramInitData = tg.initData
        // A previous browser/password token must not replace this Telegram session.
        localStorage.removeItem("lora_token")
      }
    } catch (e) {
      console.warn("[TMA] Error during Telegram WebApp setup:", e)
    }
  }
}

api.interceptors.request.use(async (config) => {
  let token = localStorage.getItem("lora_token")
  // Prevent an initial burst of API calls from racing Telegram authentication.
  if (!token && telegramInitData) token = await authenticateTelegram()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config as (typeof err.config & { _telegramRetry?: boolean }) | undefined
    if (err.response?.status === 401 && original && !original._telegramRetry && telegramInitData && !original.url?.includes("/api/auth/telegram")) {
      original._telegramRetry = true
      localStorage.removeItem("lora_token")
      const token = await authenticateTelegram()
      if (token) {
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${token}`
        return api.request(original)
      }
    }
    if (err.response?.status === 401) localStorage.removeItem("lora_token")
    return Promise.reject(err)
  },
)
