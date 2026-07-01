import { twMerge } from "tailwind-merge"

interface SpinnerProps {
  size?: "sm" | "md" | "lg"
  className?: string
}

const sizes = { sm: "w-4 h-4", md: "w-6 h-6", lg: "w-10 h-10" }

export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <div className={twMerge("flex items-center justify-center", className)}>
      <svg className={twMerge("animate-spin text-text-secondary", sizes[size])} viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  )
}
