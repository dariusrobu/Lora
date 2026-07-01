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
        "rounded-2xl p-6 backdrop-blur-2xl bg-surface border border-border shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]",
        onClick && "cursor-pointer",
        className,
      )}
    >
      {children}
    </div>
  )
}
