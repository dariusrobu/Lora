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
      <div className="bg-[#08080e]/80 backdrop-blur-2xl rounded-2xl shadow-[0_16px_40px_rgba(0,0,0,0.6)] px-3 py-2 flex items-center justify-around border border-white/[0.06]">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === "/"} className="flex-1">
            {({ isActive }) => (
              <motion.div
                whileTap={{ scale: 0.9 }}
                className={twMerge(
                  "flex flex-col items-center gap-1 py-1.5 px-2 rounded-xl transition-all",
                  isActive
                    ? "text-white bg-white/[0.06] border border-white/[0.08]"
                    : "text-text-muted hover:text-white border border-transparent",
                )}
              >
                <Icon className={twMerge("w-4 h-4 transition-colors", isActive ? "text-indigo-400" : "text-text-muted")} />
                <span className={twMerge(
                  "text-[10px] font-medium tracking-wide transition-colors",
                  isActive ? "text-white" : "text-text-muted",
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
