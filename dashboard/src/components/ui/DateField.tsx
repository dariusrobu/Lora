import { forwardRef } from "react"
import { CalendarDays } from "lucide-react"
import { twMerge } from "tailwind-merge"

/**
 * Shared date-only field.
 *
 * The API always receives an ISO date (YYYY-MM-DD). Keeping this in one
 * component prevents individual pages from applying different date styles or
 * accidentally sending locale-formatted dates.
 */
interface DateFieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string
}

export const DateField = forwardRef<HTMLInputElement, DateFieldProps>(({ className, label, onChange, ...props }, ref) => {
  const setRelativeDate = (offset: number) => {
    const value = new Date()
    value.setDate(value.getDate() + offset)
    const next = value.toISOString().slice(0, 10)
    onChange?.({ target: { value: next } } as React.ChangeEvent<HTMLInputElement>)
  }
  return (
  <label className={twMerge("block", label && "space-y-1.5", props.disabled && "cursor-not-allowed")}>
    {label && <span className="block text-sm text-text-secondary">{label}</span>}
    <span className="relative block">
      <CalendarDays aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-text-muted" />
      <input
        {...props}
        onChange={onChange}
        ref={ref}
        type="date"
        inputMode="numeric"
        lang="ro-RO"
        aria-label={props["aria-label"] ?? label}
        className={twMerge(
          "h-11 w-full rounded-xl border border-border bg-surface pl-10 pr-3 text-text-primary",
          "[color-scheme:light] dark:[color-scheme:dark] placeholder:text-text-muted",
          "focus:border-primary/30 focus:outline-none focus:ring-1 focus:ring-primary/20",
          "transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60",
          className,
        )}
      />
    </span>
    <span className="mt-1 flex gap-1 text-[11px] text-text-muted">
      <button type="button" className="rounded-md px-1.5 py-0.5 hover:bg-surface-hover" onClick={() => setRelativeDate(0)}>Azi</button>
      <button type="button" className="rounded-md px-1.5 py-0.5 hover:bg-surface-hover" onClick={() => setRelativeDate(1)}>Mâine</button>
      <button type="button" className="rounded-md px-1.5 py-0.5 hover:bg-surface-hover" onClick={() => onChange?.({ target: { value: "" } } as React.ChangeEvent<HTMLInputElement>)}>Șterge</button>
    </span>
  </label>
  )
})

DateField.displayName = "DateField"
