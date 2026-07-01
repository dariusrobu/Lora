import { motion } from "framer-motion"
import { ChevronLeft } from "lucide-react"

interface ViewContainerProps {
  children: React.ReactNode
  title: string
  onBack: () => void
}

export function ViewContainer({ children, title, onBack }: ViewContainerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 1.02 }}
      className="fixed inset-0 bg-bg z-[100] overflow-y-auto"
    >
      <div className="sticky top-0 z-10 glass-strong backdrop-blur-2xl border-b border-border">
        <div className="max-w-4xl mx-auto flex items-center h-[52px] px-4">
          <motion.button
            onClick={onBack}
            whileTap={{ scale: 0.97 }}
            className="flex items-center gap-0.5 text-apple-body text-primary hover:text-primary/80 transition-colors -ml-2 min-h-[44px] min-w-[44px]"
          >
            <ChevronLeft className="w-6 h-6" />
            <span className="text-apple-callout">Back</span>
          </motion.button>
          <h2 className="flex-1 text-center text-apple-headline font-semibold text-text-primary tracking-apple pr-[72px]">{title}</h2>
        </div>
      </div>
      <div className="max-w-4xl mx-auto p-4 lg:p-8">
        {children}
      </div>
    </motion.div>
  )
}
