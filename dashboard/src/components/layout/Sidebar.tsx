import { NavLink } from "react-router-dom"
import { twMerge } from "tailwind-merge"
import {
  LayoutDashboard, ClipboardList, Heart, Brain, Compass, GraduationCap, Settings2, MessageCircle,
} from "lucide-react"

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/plan", label: "Plan", icon: ClipboardList },
  { to: "/body", label: "Body", icon: Heart },
  { to: "/mind", label: "Mind", icon: Brain },
  { to: "/life", label: "Life", icon: Compass },
  { to: "/university", label: "University", icon: GraduationCap },
  { to: "/space", label: "Space", icon: Settings2 },
  { to: "/chat", label: "Vorbește cu Lora", icon: MessageCircle },
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
        <div className="flex items-center justify-between px-6 h-16 border-b border-border/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary to-accent flex items-center justify-center shrink-0 shadow-glow-indigo">
              <span className="text-sm font-bold text-white tracking-wider">L</span>
            </div>
            <div>
              <span className="font-semibold text-base tracking-tight text-text-primary flex items-center gap-1.5">
                Lora
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-primary/20 text-primary font-mono font-medium border border-primary/30">
                  AI
                </span>
              </span>
            </div>
          </div>
        </div>
        <nav className="p-3 space-y-1 overflow-y-auto h-[calc(100%-4rem)]">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={onClose}>
              {({ isActive }) => (
                <div className={twMerge(
                  "group flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs transition-all duration-200 ease-apple",
                  isActive
                    ? "font-semibold text-text-primary bg-primary/15 border border-primary/30 shadow-[0_0_16px_rgba(99,102,241,0.2)]"
                    : "text-text-secondary hover:text-text-primary hover:bg-black/[0.04] dark:hover:bg-white/[0.035] border border-transparent",
                )}>
                  <Icon className={twMerge(
                    "w-4 h-4 shrink-0 transition-colors",
                    isActive ? "text-primary" : "text-text-muted group-hover:text-text-primary",
                  )} />
                  <span>{label}</span>
                </div>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
