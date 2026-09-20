import { useState } from "react"
import { Outlet, useLocation } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Sidebar } from "./Sidebar"
import { Header } from "./Header"
import { MobileTabBar } from "./MobileTabBar"
import { NotificationProvider } from "../../context/NotificationContext"
import { ChatDock } from "../ChatDock"

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  return (
    <NotificationProvider>
      <div className="min-h-screen bg-bg text-text-primary transition-colors">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className={sidebarOpen ? "lg:ml-64" : "lg:ml-0"}>
          <Header onMenu={() => setSidebarOpen(!sidebarOpen)} sidebarOpen={sidebarOpen} />
          <div className="max-w-5xl mx-auto p-4 md:p-6 pb-32 lg:pb-10">
            <main>
              <AnimatePresence mode="wait">
                <motion.div
                  key={location.pathname}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.2 }}
                >
                  <Outlet />
                </motion.div>
              </AnimatePresence>
            </main>
          </div>
        </div>
        <MobileTabBar />
        <ChatDock />
      </div>
    </NotificationProvider>
  )
}
