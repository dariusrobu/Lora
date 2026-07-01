import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react"

type ThemeMode = "dark" | "light" | "auto"

interface ThemeContextValue {
  mode: ThemeMode
  resolvedTheme: "dark" | "light"
  cycleMode: () => void
  setMode: (t: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function getInitialMode(): ThemeMode {
  if (typeof window === "undefined") return "auto"
  const old = localStorage.getItem("lora_theme")
  if (old === "dark" || old === "light") {
    localStorage.removeItem("lora_theme")
    localStorage.setItem("lora_theme_mode", old)
    return old
  }
  const stored = localStorage.getItem("lora_theme_mode")
  if (stored === "dark" || stored === "light" || stored === "auto") return stored
  return "auto"
}

function resolveTheme(mode: ThemeMode): "dark" | "light" {
  if (mode !== "auto") return mode
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(getInitialMode)
  const [resolvedTheme, setResolvedTheme] = useState<"dark" | "light">(() => resolveTheme(mode))

  useEffect(() => {
    const root = document.documentElement
    if (resolvedTheme === "dark") {
      root.classList.add("dark")
    } else {
      root.classList.remove("dark")
    }
  }, [resolvedTheme])

  useEffect(() => {
    localStorage.setItem("lora_theme_mode", mode)
  }, [mode])

  useEffect(() => {
    if (mode !== "auto") {
      setResolvedTheme(mode)
      return
    }
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const handler = (e: MediaQueryListEvent) => setResolvedTheme(e.matches ? "dark" : "light")
    mq.addEventListener("change", handler)
    handler({ matches: mq.matches } as MediaQueryListEvent)
    return () => mq.removeEventListener("change", handler)
  }, [mode])

  const cycleMode = useCallback(() => {
    setModeState((prev) => {
      if (prev === "dark") return "light"
      if (prev === "light") return "auto"
      return "dark"
    })
  }, [])

  const setMode = useCallback((t: ThemeMode) => setModeState(t), [])

  return (
    <ThemeContext.Provider value={{ mode, resolvedTheme, cycleMode, setMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider")
  return ctx
}
