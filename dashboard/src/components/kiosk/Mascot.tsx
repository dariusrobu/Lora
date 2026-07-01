import { motion } from "framer-motion"
import { useState } from "react"

function getState(): "morning" | "evening" | "happy" | "neutral" {
  const h = new Date().getHours()
  if (h < 12) return "morning"
  if (h >= 20) return "evening"
  return "neutral"
}

const eyes = {
  morning: "M 18 30 Q 22 26 26 30",
  evening: "M 18 30 Q 22 34 26 30",
  happy: "M 18 28 Q 22 24 26 28",
  neutral: "M 18 30 Q 22 30 26 30",
}

const mouth = {
  morning: "M 16 40 Q 22 46 28 40",
  evening: "M 16 40 Q 22 38 28 40",
  happy: "M 14 40 Q 22 50 30 40",
  neutral: "M 18 40 Q 22 42 26 40",
}

export default function Mascot() {
  const [state, setState] = useState<"morning" | "evening" | "happy" | "neutral">(getState())

  const handleTap = () => {
    setState("happy")
    setTimeout(() => setState(getState()), 1500)
  }

  return (
    <motion.button
      onClick={handleTap}
      className="relative w-24 h-24 mx-auto block outline-none"
      whileTap={{ scale: 0.9 }}
      aria-label="Mascot"
    >
      <svg viewBox="0 0 64 64" className="w-full h-full drop-shadow-[0_0_12px_rgba(168,85,247,0.4)]">
        {/* Ring */}
        <motion.ellipse
          cx="32" cy="32" rx="38" ry="10"
          fill="none" stroke="rgba(168,85,247,0.3)" strokeWidth="3"
          transform="rotate(-20 32 32)"
          animate={{ rotate: [-20, -15, -20] }}
          transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
        />
        {/* Planet body */}
        <motion.circle
          cx="32" cy="32" r="18"
          fill="url(#planetGrad)"
          animate={{ scale: [1, 1.03, 1] }}
          transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
        />
        {/* Eye */}
        <path d={eyes[state]} fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
        {/* Mouth */}
        <path d={mouth[state]} fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
        {/* Cheeks */}
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
