import { createContext, useContext, useState, useCallback, type ReactNode } from "react"
import { DynamicIsland } from "../components/DynamicIsland"
import { type LucideIcon } from "lucide-react"

interface Notification {
  message: string
  icon: LucideIcon
}

interface NotificationContextValue {
  notify: (message: string, icon: LucideIcon) => void
}

const NotificationContext = createContext<NotificationContextValue>({ notify: () => {} })

export function useNotify() {
  return useContext(NotificationContext)
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notification, setNotification] = useState<Notification | null>(null)

  const notify = useCallback((message: string, icon: LucideIcon) => {
    setNotification({ message, icon })
    setTimeout(() => setNotification(null), 2500)
  }, [])

  return (
    <NotificationContext.Provider value={{ notify }}>
      {children}
      <DynamicIsland
        active={!!notification}
        message={notification?.message ?? ""}
        icon={notification?.icon ?? null}
      />
    </NotificationContext.Provider>
  )
}
