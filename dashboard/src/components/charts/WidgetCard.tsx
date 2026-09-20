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
    <div className={twMerge("relative group py-4 transition-all duration-300", className)}>
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="text-indigo-400 flex items-center justify-center shrink-0">
            {icon}
          </div>
          <h3 className="text-[11px] font-bold text-white uppercase tracking-wider">{label}</h3>
        </div>
        <div className="flex items-center gap-1 opacity-50 group-hover:opacity-100 transition-opacity">
          {onExpand && (
            <motion.button
              onClick={onExpand}
              whileTap={{ scale: 0.9 }}
              className="p-1.5 rounded-lg text-text-muted hover:text-white hover:bg-white/[0.06] transition-colors"
              title="Extinde"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </motion.button>
          )}
          <Link to={linkTo} className="p-1.5 rounded-lg text-text-muted hover:text-white hover:bg-white/[0.06] transition-colors" title="Deschide">
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
