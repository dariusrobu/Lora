import { motion, AnimatePresence } from "framer-motion"
import { X } from "lucide-react"

interface BottomSheetProps {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
}

export function BottomSheet({ open, onClose, title, children }: BottomSheetProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="bottom-sheet"
          className="fixed inset-0 z-50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            key="bottom-sheet-content"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 200 }}
            dragElastic={0.2}
            onDragEnd={(e, info) => {
              if (info.offset.y > 80) onClose()
            }}
            className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-bg border border-border border-b-0 shadow-2xl"
          >
            <div className="flex flex-col items-center pt-2 pb-1">
              <div className="w-8 h-1 rounded-full bg-text-muted/40 mb-3" />
              <div className="w-full px-5 pb-4 flex items-center justify-between border-b border-border">
                {title ? (
                  <h2 className="text-apple-headline text-text-primary tracking-apple">{title}</h2>
                ) : (
                  <div />
                )}
                <button onClick={onClose} className="p-1 -mr-1 hover:bg-surface rounded-lg transition-colors">
                  <X className="w-5 h-5 text-text-muted" />
                </button>
              </div>
            </div>
            <div className="p-5 pt-4">
              {children}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}