import { twMerge } from "tailwind-merge"

interface BadgeProps {
  children: React.ReactNode
  variant?: "default" | "highlight" | "muted"
  className?: string
}

const variants = {
  default: "bg-surface text-text-secondary",
  highlight: "bg-surface text-text-primary",
  muted: "bg-surface text-text-muted",
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span className={twMerge("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium", variants[variant], className)}>
      {children}
    </span>
  )
}
