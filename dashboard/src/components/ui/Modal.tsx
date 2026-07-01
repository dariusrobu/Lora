import { useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { X } from "lucide-react"

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
}

export function Modal({ open, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => { document.body.style.overflow = "" }
  }, [open])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="relative w-full max-w-lg rounded-2xl border border-border bg-bg p-6 shadow-2xl shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
          >
            <div className="flex items-center justify-between mb-4">
              {title && <h2 className="text-lg font-semibold text-text-primary">{title}</h2>}
              <button onClick={onClose} className="p-1 hover:bg-surface rounded-lg transition-colors">
                <X className="w-5 h-5 text-text-muted" />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
