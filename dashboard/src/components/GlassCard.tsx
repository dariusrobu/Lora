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
        "rounded-2xl p-6 bg-black/[0.02] dark:bg-white/[0.018] hover:bg-black/[0.035] dark:hover:bg-white/[0.03] border border-border-light hover:border-border transition-all duration-300",
        onClick && "cursor-pointer",
        className,
      )}
    >
      {children}
    </div>
  )
}
