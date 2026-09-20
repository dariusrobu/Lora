import { useEffect } from "react"
import BrailleSamurai from "../components/kiosk/BrailleSamurai"
import TerminalData from "../components/kiosk/TerminalData"

export default function KioskPage() {
  useEffect(() => {
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = ""
    }
  }, [])

  return (
    <div className="fixed inset-0 bg-black text-white font-mono overflow-hidden select-none">
      <BrailleSamurai />
      <div className="fixed right-0 top-0 h-full w-96 bg-black/60 backdrop-blur-md border-l border-white/10 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        <TerminalData />
      </div>
    </div>
  )
}
