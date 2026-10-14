import { NavLink } from "react-router-dom"
import { CalendarDays, FolderKanban, GraduationCap, House, NotebookTabs } from "lucide-react"

const navItems = [
  { to: "/", label: "Azi", icon: House },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/projects", label: "Proiecte", icon: FolderKanban },
  { to: "/journal", label: "Jurnal", icon: NotebookTabs },
  { to: "/university", label: "Facultate", icon: GraduationCap },
]

export function MobileTabBar() {
  return <nav className="daily-mobile-nav" aria-label="Navigație principală">{navItems.map(({ to, label, icon: Icon }) => <NavLink to={to} end={to === "/"} key={to} className={({ isActive }) => `daily-mobile-link ${isActive ? "active" : ""}`}><Icon size={21} strokeWidth={1.8} /><span>{label}</span></NavLink>)}</nav>
}
