import { useState, useEffect } from "react"
import { motion } from "framer-motion"

const days = ["Duminică", "Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă"]
const months = ["Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie", "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie"]

function Mascot() {
  const [happy, setHappy] = useState(false)

  return (
    <motion.button
      onClick={() => { setHappy(true); setTimeout(() => setHappy(false), 1500) }}
      className="mt-2 outline-none"
      whileTap={{ scale: 0.9 }}
      aria-label="Mascot"
    >
      <svg viewBox="0 0 64 64" className="w-10 h-10 drop-shadow-[0_0_8px_rgba(168,85,247,0.3)]">
        <motion.ellipse
          cx="32" cy="32" rx="38" ry="10"
          fill="none" stroke="rgba(168,85,247,0.25)" strokeWidth="2"
          transform="rotate(-20 32 32)"
          animate={{ rotate: [-20, -15, -20] }}
          transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
        />
        <motion.circle
          cx="32" cy="32" r="18"
          fill="url(#planetGrad)"
          animate={{ scale: [1, 1.03, 1] }}
          transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
        />
        <path d={happy ? "M 18 28 Q 22 24 26 28" : "M 18 30 Q 22 30 26 30"} fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
        <path d={happy ? "M 14 40 Q 22 50 30 40" : "M 16 40 Q 22 38 28 40"} fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
        <circle cx="14" cy="36" r="3" fill="rgba(255,255,255,0.1)" />
        <circle cx="50" cy="36" r="3" fill="rgba(255,255,255,0.1)" />
        <defs>
          <radialGradient id="planetGrad" cx="35%" cy="35%">
            <stop offset="0%" stopColor="#a855f7" />
            <stop offset="50%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#6d28d9" />
          </radialGradient>
        </defs>
      </svg>
    </motion.button>
  )
}

export default function ClockWidget() {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const h = String(now.getHours()).padStart(2, "0")
  const m = String(now.getMinutes()).padStart(2, "0")
  const s = String(now.getSeconds()).padStart(2, "0")

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="text-7xl font-light leading-none tabular-nums">
        {h}:{m}<span className="text-3xl font-light opacity-40">:{s}</span>
      </div>
      <div className="mt-3 text-base font-semibold tracking-[1.5px] uppercase opacity-60">
        {days[now.getDay()]}
      </div>
      <div className="text-base opacity-40 mt-1">
        {now.getDate()} {months[now.getMonth()]}
      </div>
      <Mascot />
    </div>
  )
}
