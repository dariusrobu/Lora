import { Sun, Moon, Monitor } from "lucide-react"
import { useTheme } from "../../context/ThemeContext"

export function Header() {
  const { mode, cycleMode } = useTheme()

  return (
    <header className="sticky top-0 z-20 h-14 border-b border-border/40 bg-bg/75 backdrop-blur-2xl px-4 flex items-center justify-between transition-colors duration-300 ease-apple">
      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>Lora AI Online</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={cycleMode}
          className="p-2 hover:bg-black/[0.04] dark:hover:bg-white/[0.05] border border-border/40 rounded-xl transition-colors text-text-secondary hover:text-text-primary"
          title={`Theme: ${mode}${mode === "auto" ? " (follows system)" : ""}`}
        >
          {mode === "dark" ? <Moon className="w-4 h-4" /> : mode === "light" ? <Sun className="w-4 h-4" /> : <Monitor className="w-4 h-4" />}
        </button>
      </div>
    </header>
  )
}
