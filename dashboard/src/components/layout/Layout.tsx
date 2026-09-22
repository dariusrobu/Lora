import { Outlet, useLocation } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Header } from "./Header"
import { MobileTabBar } from "./MobileTabBar"
import { NotificationProvider } from "../../context/NotificationContext"

export function Layout() {
  const location = useLocation()

  return (
    <NotificationProvider>
      <div className="min-h-screen bg-bg text-text-primary transition-colors">
        <div>
          <Header />
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
      </div>
    </NotificationProvider>
  )
}
