import { PanelLeftClose, PanelLeft, Sun, Moon, Monitor } from "lucide-react"
import { useTheme } from "../../context/ThemeContext"

interface HeaderProps {
  onMenu: () => void
  sidebarOpen?: boolean
}

export function Header({ onMenu, sidebarOpen }: HeaderProps) {
  const { mode, cycleMode } = useTheme()

  return (
    <header className="sticky top-0 z-20 h-14 border-b border-border bg-bg/90 backdrop-blur-md px-4 flex items-center justify-between transition-colors duration-300 ease-apple">
      <button onClick={onMenu} className="p-2 hover:bg-surface rounded-lg transition-colors">
        {sidebarOpen ? <PanelLeftClose className="w-5 h-5 text-text-primary" /> : <PanelLeft className="w-5 h-5 text-text-primary" />}
      </button>
      <div className="hidden lg:block" />
      <div className="flex items-center gap-2">
        <button
          onClick={cycleMode}
          className="p-2 hover:bg-surface rounded-lg transition-colors text-text-secondary hover:text-text-primary"
          title={`Theme: ${mode}${mode === "auto" ? " (follows system)" : ""}`}
        >
          {mode === "dark" ? <Moon className="w-4 h-4" /> : mode === "light" ? <Sun className="w-4 h-4" /> : <Monitor className="w-4 h-4" />}
        </button>
      </div>
    </header>
  )
}
