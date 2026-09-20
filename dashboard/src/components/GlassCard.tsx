import { twMerge } from "tailwind-merge"

interface GlassCardProps {
  children: React.ReactNode
  className?: string
  onClick?: () => void
}

export function GlassCard({ children, className, onClick }: GlassCardProps) {
  return (
    <div
      onClick={onClick}
      className={twMerge(
        "rounded-2xl p-6 bg-white/[0.018] hover:bg-white/[0.03] border border-white/[0.04] hover:border-white/[0.08] transition-all duration-300",
        onClick && "cursor-pointer",
        className,
      )}
    >
      {children}
    </div>
  )
}
