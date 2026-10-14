import { NavLink, Outlet } from "react-router-dom"
import { CalendarDays, FolderKanban, GraduationCap, House, NotebookTabs } from "lucide-react"
import { MobileTabBar } from "./MobileTabBar"
import { NotificationProvider } from "../../context/NotificationContext"
import { CommandPalette } from "../CommandPalette"
import { useState, useEffect } from "react"
import "./daily.css"

const navigation = [
  { to: "/", label: "Azi", icon: House },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/projects", label: "Proiecte", icon: FolderKanban },
  { to: "/journal", label: "Jurnal", icon: NotebookTabs },
  { to: "/university", label: "Facultate", icon: GraduationCap },
]

export function Layout() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  useEffect(() => { const onKey = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPaletteOpen(true) } }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey) }, [])

  return (
    <NotificationProvider>
      <div className="daily-shell">
        <div className="daily-container">
          <nav className="daily-desktop-nav" aria-label="Navigație principală">{navigation.map(({ to, label, icon: Icon }) => <NavLink to={to} end={to === "/"} key={to} className={({ isActive }) => `daily-desktop-link ${isActive ? "active" : ""}`}><Icon size={17} strokeWidth={1.8} />{label}</NavLink>)}</nav>
          <main id="main-content"><Outlet /></main>
        </div>
        <MobileTabBar />
        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      </div>
    </NotificationProvider>
  )
}
