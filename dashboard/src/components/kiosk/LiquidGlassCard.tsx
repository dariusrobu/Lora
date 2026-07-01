import type { ReactNode } from "react"

interface Props {
  children: ReactNode
  className?: string
  tint?: "purple" | "amber" | "green" | "blue" | "neutral"
}

const gradients: Record<string, string> = {
  purple: "bg-gradient-to-br from-purple-700/40 via-purple-900/20 to-transparent",
  amber: "bg-gradient-to-br from-amber-600/40 via-amber-800/20 to-transparent",
  green: "bg-gradient-to-br from-emerald-600/40 via-emerald-800/20 to-transparent",
  blue: "bg-gradient-to-br from-blue-600/40 via-blue-800/20 to-transparent",
  neutral: "bg-[#1c1c2e]",
}

export default function LiquidGlassCard({ children, className = "", tint = "neutral" }: Props) {
  return (
    <div className={`card-liquid h-full ${gradients[tint]} ${className}`}>
      <div className="card-liquid-content p-5 flex flex-col">
        {children}
      </div>
    </div>
  )
}
