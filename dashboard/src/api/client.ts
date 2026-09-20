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

// Telegram WebApp authentication exchanges signed initData for a short-lived JWT.
if (typeof window !== "undefined") {
  const tg = (window as unknown as { Telegram?: { WebApp?: { ready?: () => void; expand?: () => void; initData?: string } } }).Telegram?.WebApp
  if (tg) {
    try {
      tg.ready?.()
      tg.expand?.()
      // If no token stored yet, exchange initData for a JWT
      if (!localStorage.getItem("lora_token") && tg.initData) {
        axios.post(`${BASE_URL}/api/auth/telegram`, { init_data: tg.initData }, {
          headers: {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",
          },
        }).then((res) => {
          if (res.data?.access_token) {
            localStorage.setItem("lora_token", res.data.access_token)
            window.location.reload()
          }
        }).catch((err) => {
          console.warn("[TMA] Telegram auto-login failed:", err)
        })
      }
    } catch (e) {
      console.warn("[TMA] Error during Telegram WebApp setup:", e)
    }
  }
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("lora_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("lora_token")
    }
    return Promise.reject(err)
  },
)
