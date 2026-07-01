import { useEffect } from "react"
import AsciiPlanet from "../components/kiosk/AsciiPlanet"
import TerminalData from "../components/kiosk/TerminalData"

export default function KioskPage() {
  useEffect(() => {
    document.body.style.overflow = "hidden"
    const orig = document.documentElement.style.fontSize
    document.documentElement.style.fontSize = "200%"
    return () => {
      document.documentElement.style.fontSize = orig
      document.body.style.overflow = ""
    }
  }, [])

  return (
    <div className="fixed inset-0 bg-black text-white font-mono overflow-hidden select-none">
      <div className="h-full grid grid-cols-5">
        <div className="col-span-3 h-full min-h-0">
          <AsciiPlanet />
        </div>
        <div className="col-span-2 h-full min-h-0 flex items-center overflow-hidden">
          <TerminalData />
        </div>
      </div>
    </div>
  )
}
