import { NavLink } from "react-router-dom"
import { twMerge } from "tailwind-merge"
import { motion } from "framer-motion"
import {
  LayoutDashboard, ClipboardList, Heart, Brain, Compass, GraduationCap,
} from "lucide-react"

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/plan", label: "Plan", icon: ClipboardList },
  { to: "/body", label: "Body", icon: Heart },
  { to: "/mind", label: "Mind", icon: Brain },
  { to: "/life", label: "Life", icon: Compass },
  { to: "/university", label: "University", icon: GraduationCap },
]

export function MobileTabBar() {
  return (
    <motion.nav
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 28, delay: 0.2 }}
      className="fixed bottom-4 left-4 right-4 z-50 lg:hidden"
    >
      <div className="glass-strong rounded-2xl shadow-apple-heavy backdrop-blur-3xl px-2 py-1.5 flex items-center justify-around border border-white/30 dark:border-white/[0.08]">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === "/"} className="flex-1">
            {({ isActive }) => (
              <motion.div
                whileTap={{ scale: 0.9 }}
                className={twMerge(
                  "flex flex-col items-center gap-0.5 py-1.5 px-2 rounded-xl transition-colors",
                  isActive
                    ? "text-primary"
                    : "text-text-muted",
                )}
              >
                <Icon className={twMerge("w-5 h-5", isActive && "drop-shadow-sm")} />
                <span className={twMerge(
                  "text-[9px] font-semibold uppercase tracking-wider",
                  isActive ? "text-primary" : "text-text-muted",
                )}>
                  {label}
                </span>
              </motion.div>
            )}
          </NavLink>
        ))}
      </div>
    </motion.nav>
  )
}
