import type { ReactNode } from "react"
import { motion } from "framer-motion"
import { Link } from "react-router-dom"
import { twMerge } from "tailwind-merge"
import { Maximize2, ArrowRight, AlertCircle, RefreshCw } from "lucide-react"
import { SkeletonWidget } from "./SkeletonWidget"

interface WidgetCardProps {
  icon: ReactNode
  label: string
  linkTo: string
  onExpand?: () => void
  isLoading?: boolean
  isError?: boolean
  isEmpty?: boolean
  emptyMessage?: string
  emptyCTA?: ReactNode
  errorMessage?: string
  onRetry?: () => void
  children?: ReactNode
  className?: string
}

export function WidgetCard({
  icon, label, linkTo, onExpand,
  isLoading, isError, isEmpty,
  emptyMessage = "No data",
  emptyCTA,
  errorMessage = "Could not load",
  onRetry,
  children, className,
}: WidgetCardProps) {
  return (
    <div className={twMerge("glass-strong rounded-2xl p-4 shadow-apple-heavy", className)}>
      <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-text-muted shrink-0">{icon}</span>
            <h3 className="text-apple-footnote font-semibold text-text-secondary uppercase tracking-widest">{label}</h3>
          </div>
          <div className="flex items-center gap-0.5">
            {onExpand && (
              <motion.button
                onClick={onExpand}
                whileTap={{ scale: 0.9 }}
                className="p-1.5 rounded-full text-text-muted hover:text-text-primary hover:bg-white/10 dark:hover:bg-white/[0.08] transition-colors"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </motion.button>
            )}
            <Link to={linkTo} className="p-1.5 rounded-full text-text-muted hover:text-text-primary hover:bg-white/10 dark:hover:bg-white/[0.08] transition-colors">
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
        {isLoading ? (
          <SkeletonWidget />
        ) : isError ? (
          <div className="flex flex-col items-center py-4 text-center">
            <AlertCircle className="w-8 h-8 text-text-muted mb-2" />
            <p className="text-apple-caption1 text-text-muted mb-2">{errorMessage}</p>
            {onRetry && (
              <motion.button
                onClick={onRetry}
                whileTap={{ scale: 0.95 }}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full glass-strong text-apple-caption2 font-medium text-primary"
              >
                <RefreshCw className="w-3 h-3" /> Retry
              </motion.button>
            )}
          </div>
        ) : isEmpty ? (
          <div className="flex flex-col items-center py-4 text-center">
            {icon}
            <p className="text-apple-caption1 text-text-muted mb-3 mt-2">{emptyMessage}</p>
            {emptyCTA}
          </div>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            {children}
          </motion.div>
        )}
    </div>
  )
}
