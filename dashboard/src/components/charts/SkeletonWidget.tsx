import { twMerge } from "tailwind-merge"

export function SkeletonWidget({ className }: { className?: string }) {
  return (
    <div className={twMerge("animate-pulse space-y-3", className)}>
      <div className="flex items-center justify-between">
        <div className="h-3 w-20 rounded-full bg-white/10 dark:bg-white/[0.06]" />
        <div className="h-3 w-12 rounded-full bg-white/10 dark:bg-white/[0.06]" />
      </div>
      <div className="h-8 w-24 rounded-lg bg-white/10 dark:bg-white/[0.06]" />
      <div className="h-2 w-full rounded-full bg-white/10 dark:bg-white/[0.06]" />
      <div className="h-2 w-3/4 rounded-full bg-white/10 dark:bg-white/[0.06]" />
    </div>
  )
}
