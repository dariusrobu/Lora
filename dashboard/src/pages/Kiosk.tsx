import { useEffect } from "react"
import { motion } from "framer-motion"
import ClockWidget from "../components/kiosk/ClockWidget"
import WeatherWidget from "../components/kiosk/WeatherWidget"
import TasksWidget from "../components/kiosk/TasksWidget"
import ServerStatusWidget from "../components/kiosk/ServerStatusWidget"
import HealthWidget from "../components/kiosk/HealthWidget"
import DownloadsWidget from "../components/kiosk/DownloadsWidget"
import TodaySchedule from "../components/kiosk/TodaySchedule"
import FinanceWidget from "../components/kiosk/FinanceWidget"

import LiquidGlassCard from "../components/kiosk/LiquidGlassCard"
import { WidgetErrorBoundary } from "../components/kiosk/WidgetErrorBoundary"

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.15 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 14, scale: 0.97 },
  show: {
    opacity: 1, y: 0, scale: 1,
    transition: { type: "spring", damping: 22, stiffness: 200 },
  },
}

export default function KioskPage() {
  useEffect(() => {
    document.body.style.overflow = "hidden"
    const orig = document.documentElement.style.fontSize
    document.documentElement.style.fontSize = "150%"
    return () => {
      document.documentElement.style.fontSize = orig
      document.body.style.overflow = ""
    }
  }, [])

  return (
    <div
      className="fixed inset-0 overflow-hidden bg-gradient-to-b from-[#0d1117] to-[#161b22] text-white"
      style={{
        "--color-text-primary": "#f5f5f7",
        "--color-text-secondary": "rgba(245,245,247,0.4)",
        "--color-text-muted": "rgba(245,245,247,0.2)",
      } as React.CSSProperties}
    >
      <motion.div
        className="relative z-10 h-full flex flex-col px-10 py-6 mx-auto max-w-[2200px]"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <div className="flex-1 grid grid-cols-4 gap-4 min-h-0">
          {/* Row 1: Clock | Weather | Tasks | Health */}
          <motion.div variants={itemVariants} className="h-full">
            <LiquidGlassCard tint="neutral">
              <WidgetErrorBoundary><ClockWidget /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>
          <motion.div variants={itemVariants} className="h-full">
            <LiquidGlassCard tint="blue">
              <WidgetErrorBoundary><WeatherWidget /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>
          <motion.div variants={itemVariants} className="h-full">
            <LiquidGlassCard tint="amber">
              <WidgetErrorBoundary><TasksWidget /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>
          <motion.div variants={itemVariants} className="h-full">
            <LiquidGlassCard tint="green">
              <WidgetErrorBoundary><HealthWidget /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>

          {/* Row 2: ServerStatus full width */}
          <motion.div variants={itemVariants} className="col-span-4 h-full">
            <LiquidGlassCard tint="purple">
              <WidgetErrorBoundary><ServerStatusWidget /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>

          {/* Row 3: Downloads | Schedule (2×) | Finance */}
          <motion.div variants={itemVariants} className="h-full">
            <LiquidGlassCard tint="blue">
              <WidgetErrorBoundary><DownloadsWidget /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>
          <motion.div variants={itemVariants} className="col-span-2 h-full">
            <LiquidGlassCard tint="neutral">
              <WidgetErrorBoundary><TodaySchedule /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>
          <motion.div variants={itemVariants} className="h-full">
            <LiquidGlassCard tint="purple">
              <WidgetErrorBoundary><FinanceWidget /></WidgetErrorBoundary>
            </LiquidGlassCard>
          </motion.div>

        </div>
      </motion.div>


    </div>
  )
}
