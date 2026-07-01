import { twMerge } from "tailwind-merge"
import { type VariantProps, cva } from "class-variance-authority"
import { forwardRef } from "react"

const btn = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary: "bg-blue-600 text-white hover:brightness-110 shadow-lg shadow-blue-600/20 dark:shadow-black/30",
        secondary: "bg-surface hover:bg-surface text-text-secondary hover:text-text-primary border border-border",
        ghost: "hover:bg-surface text-text-secondary hover:text-text-primary",
        danger: "bg-surface text-text-secondary hover:text-red-400 hover:bg-surface border border-border",
      },
      size: { sm: "h-8 px-3 text-xs", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-base" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
)

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof btn> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => (
  <button ref={ref} className={twMerge(btn({ variant, size }), className)} {...props} />
))
Button.displayName = "Button"
