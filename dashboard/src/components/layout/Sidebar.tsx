import { NavLink } from "react-router-dom"
import { twMerge } from "tailwind-merge"
import {
  LayoutDashboard, ClipboardList, Heart, Brain, Compass, GraduationCap, Settings2,
} from "lucide-react"

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/plan", label: "Plan", icon: ClipboardList },
  { to: "/body", label: "Body", icon: Heart },
  { to: "/mind", label: "Mind", icon: Brain },
  { to: "/life", label: "Life", icon: Compass },
  { to: "/university", label: "University", icon: GraduationCap },
  { to: "/space", label: "Space", icon: Settings2 },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />}
      <aside className={twMerge(
        "fixed z-40 w-64 transition-transform duration-300 ease-apple",
        "top-0 left-0 h-full",
        "glass-strong border-r border-border/50",
        "shadow-apple-heavy",
        open ? "translate-x-0 lg:translate-x-0" : "-translate-x-full lg:-translate-x-full",
      )}>
        <div className="flex items-center gap-3 px-6 h-16 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center shrink-0">
            <span className="text-sm font-bold text-white">L</span>
          </div>
          <span className="font-semibold text-apple-title2 tracking-apple text-text-primary">
            Lora
          </span>
        </div>
        <nav className="p-3 space-y-0.5 overflow-y-auto h-[calc(100%-4rem)]">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={onClose}>
              {({ isActive }) => (
                <div className={twMerge(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-apple-caption1 transition-all duration-200 ease-apple",
                  isActive
                    ? "font-semibold text-text-primary border-l-2 border-l-emerald-500 bg-transparent rounded-none pl-[10px]"
                    : "text-text-secondary hover:text-text-primary",
                )}>
                  <Icon className="w-4 h-4 shrink-0" />
                  {label}
                </div>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
