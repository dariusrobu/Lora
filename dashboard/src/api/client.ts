import axios from "axios"

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ""

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("lora_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => Promise.reject(err),
)
