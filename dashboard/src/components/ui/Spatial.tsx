import { useEffect, useRef, useState, type ReactNode } from "react"
import { twMerge } from "tailwind-merge"

export function PageHeader({ title, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="mb-6 flex flex-wrap items-center justify-between gap-4"><h1 className="min-w-0 break-words text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">{title}</h1>{action}</div>
}

export function Section({ title, description, action, children, className }: { title: string; description?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={twMerge("space-y-3", className)}><div className="flex items-end justify-between gap-3"><div><h2 className="text-sm font-semibold text-text-primary">{title}</h2>{description && <p className="mt-0.5 text-xs text-text-muted">{description}</p>}</div>{action}</div>{children}</section>
}

export function Metric({ label, value, detail, className }: { label: string; value: ReactNode; detail?: ReactNode; className?: string }) {
  return <div className={twMerge("min-w-0 rounded-2xl border border-border bg-surface p-4", className)}><p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{label}</p><p className="mt-2 break-words text-xl font-semibold tracking-tight text-text-primary sm:text-2xl">{value}</p>{detail && <p className="mt-1 text-xs text-text-secondary">{detail}</p>}</div>
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="rounded-2xl border border-dashed border-border p-8 text-center"><p className="text-sm font-medium text-text-primary">{title}</p>{description && <p className="mt-1 text-xs text-text-muted">{description}</p>}{action && <div className="mt-4">{action}</div>}</div>
}

export function ModeSelector<T extends string>({ value, options, onChange }: { value: T; options: readonly { value: T; label: string }[]; onChange: (value: T) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (!open) return; const close = (event: MouseEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false) }; document.addEventListener("mousedown", close); return () => document.removeEventListener("mousedown", close) }, [open])
  const current = options.find((option) => option.value === value)?.label ?? value
  return <div ref={ref} className="relative"><button type="button" onClick={() => setOpen((state) => !state)} className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-medium text-text-secondary transition-colors hover:border-primary/30 hover:text-text-primary">{current}<span className={twMerge("text-[10px] transition-transform", open && "rotate-180")}>⌄</span></button>{open && <div className="absolute right-0 top-full z-30 mt-2 min-w-[150px] rounded-xl border border-border bg-surface p-1.5 shadow-xl">{options.map((option) => <button key={option.value} type="button" onClick={() => { onChange(option.value); setOpen(false) }} className={twMerge("block w-full rounded-lg px-3 py-2 text-left text-xs transition-colors", value === option.value ? "bg-primary/10 text-primary" : "text-text-secondary hover:bg-black/[0.04] dark:hover:bg-white/[0.05]")}>{option.label}</button>)}</div>}</div>
}
