import { twMerge } from "tailwind-merge"
import { forwardRef } from "react"

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, label, error, ...props }, ref) => (
  <div className="space-y-1.5">
    {label && <label className="text-sm text-text-secondary">{label}</label>}
    <input
      ref={ref}
      className={twMerge(
        "w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary placeholder:text-text-muted",
        "focus:outline-none focus:border-primary/30 focus:ring-1 focus:ring-primary/20",
        "transition-all duration-200",
        error && "border-red-400/30",
        className,
      )}
      {...props}
    />
    {error && <p className="text-xs text-red-400/70">{error}</p>}
  </div>
))
