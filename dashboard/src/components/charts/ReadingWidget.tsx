import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { fetchBooks, addBook, updateBook } from "../../api/queries/reading"
import { WidgetCard } from "./WidgetCard"
import { BookOpen, Plus, CheckCircle2, Bookmark, Check, Sparkles } from "lucide-react"
import type { Book } from "../../types"

interface Props {
  onExpand?: () => void
}

export function ReadingWidget({ onExpand }: Props) {
  const [quickTitle, setQuickTitle] = useState("")
  const [quickAuthor, setQuickAuthor] = useState("")
  const [showAdd, setShowAdd] = useState(false)
  const qc = useQueryClient()

  const { data: books, isLoading, isError, refetch } = useQuery<Book[]>({
    queryKey: ["books"],
    queryFn: fetchBooks,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const addMut = useMutation({
    mutationFn: addBook,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["books"] })
      setQuickTitle("")
      setQuickAuthor("")
      setShowAdd(false)
    },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: Partial<Book> }) => updateBook(id, updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["books"] })
    },
  })

  const readingBooks = books?.filter((b) => b.status === "reading") ?? []
  const doneBooks = books?.filter((b) => b.status === "done") ?? []
  const wantBooks = books?.filter((b) => b.status === "want_to_read") ?? []
  const currentBook = readingBooks[0] ?? wantBooks[0] ?? null

  const pagesRead = currentBook?.pages_read ?? 0
  const totalPages = currentBook?.total_pages ?? 0
  const pct = totalPages > 0 ? Math.min(100, Math.round((pagesRead / totalPages) * 100)) : 0
  const hasData = (books?.length ?? 0) > 0

  const handleAddPages = (pages: number) => {
    if (!currentBook) return
    const newPages = Math.min(totalPages || 9999, pagesRead + pages)
    const isFinished = totalPages > 0 && newPages >= totalPages
    updateMut.mutate({
      id: currentBook.id,
      updates: {
        pages_read: newPages,
        status: isFinished ? "done" : "reading",
      },
    })
  }

  const handleCreate = () => {
    if (!quickTitle.trim() || addMut.isPending) return
    addMut.mutate({ title: quickTitle.trim(), author: quickAuthor.trim() || undefined })
  }

  return (
    <WidgetCard
      icon={<BookOpen className="w-4 h-4" />}
      label="Reading"
      linkTo="/reading"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="Nicio carte înregistrată"
      emptyCTA={
        <motion.button
          onClick={() => setShowAdd(true)}
          whileTap={{ scale: 0.95 }}
          className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs font-medium text-indigo-400 hover:text-white transition-all"
        >
          <Plus className="w-3.5 h-3.5" /> Adaugă o carte
        </motion.button>
      }
    >
      {/* Metrics Row (3 Large Stats) */}
      <div className="grid grid-cols-3 gap-3 p-3 rounded-2xl bg-white/[0.015] border border-white/[0.04] mb-4 divide-x divide-white/[0.06]">
        <div className="flex flex-col items-center sm:items-start sm:pl-2">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Citesc</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-white tabular-nums tracking-tight">
            {readingBooks.length}
          </span>
        </div>

        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <Check className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Gata</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-emerald-400 tabular-nums tracking-tight">
            {doneBooks.length}
          </span>
        </div>

        <div className="flex flex-col items-center sm:items-start sm:px-4">
          <div className="flex items-center gap-1.5 mb-1 text-text-muted">
            <Bookmark className="w-3.5 h-3.5 text-violet-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Planificate</span>
          </div>
          <span className="text-2xl sm:text-3xl font-black text-violet-300 tabular-nums tracking-tight">
            {wantBooks.length}
          </span>
        </div>
      </div>

      {/* Hero Book Card */}
      {currentBook ? (
        <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.05] mb-3">
          <div className="flex items-start justify-between gap-3 mb-2.5">
            <div className="min-w-0 flex-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-400 mb-0.5 block">
                {currentBook.status === "reading" ? "Cartea Curentă" : "Urmează la Lectură"}
              </span>
              <h4 className="text-base font-bold text-white truncate tracking-tight">
                {currentBook.title}
              </h4>
              {currentBook.author && (
                <p className="text-xs text-zinc-400 truncate mt-0.5">{currentBook.author}</p>
              )}
            </div>

            {/* Percentage Badge */}
            {totalPages > 0 && (
              <span className="text-xl sm:text-2xl font-black bg-gradient-to-r from-indigo-300 to-purple-400 bg-clip-text text-transparent tabular-nums shrink-0">
                {pct}%
              </span>
            )}
          </div>

          {/* Progress Bar */}
          {totalPages > 0 ? (
            <div className="space-y-1.5 my-3">
              <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden p-0.5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                  className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 shadow-[0_0_12px_rgba(99,102,241,0.5)]"
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
                <span>{pagesRead} pagini citite</span>
                <span>{totalPages} pagini total</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-zinc-400 my-2">{pagesRead} pagini citite</p>
          )}

          {/* Quick Progress Buttons */}
          <div className="flex items-center gap-2 pt-2 border-t border-white/[0.04]">
            <span className="text-[10px] font-semibold uppercase text-zinc-500 tracking-wider">Adaugă:</span>
            <button
              onClick={() => handleAddPages(10)}
              disabled={updateMut.isPending}
              className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs font-bold text-zinc-300 hover:text-white border border-white/[0.06] transition-all"
            >
              +10 pag
            </button>
            <button
              onClick={() => handleAddPages(25)}
              disabled={updateMut.isPending}
              className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs font-bold text-zinc-300 hover:text-white border border-white/[0.06] transition-all"
            >
              +25 pag
            </button>
            {totalPages > 0 && pagesRead >= totalPages ? (
              <span className="ml-auto inline-flex items-center gap-1 text-xs font-bold text-emerald-400">
                <Sparkles className="w-3.5 h-3.5" /> Finalizată!
              </span>
            ) : (
              <button
                onClick={() => handleAddPages(totalPages ? totalPages - pagesRead : 50)}
                disabled={updateMut.isPending}
                className="ml-auto px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-xs font-bold text-emerald-400 border border-emerald-500/25 transition-all inline-flex items-center gap-1"
              >
                <CheckCircle2 className="w-3 h-3" /> Gata
              </button>
            )}
          </div>
        </div>
      ) : null}

      {/* Quick Add Form or Toggle */}
      <AnimatePresence>
        {showAdd ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="pt-2 border-t border-white/[0.05] space-y-2"
          >
            <div className="flex gap-2">
              <input
                value={quickTitle}
                onChange={(e) => setQuickTitle(e.target.value)}
                placeholder="Titlu carte..."
                autoFocus
                className="flex-1 bg-white/[0.03] border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-white placeholder:text-zinc-500 outline-none focus:border-indigo-400/40 transition-all"
              />
              <input
                value={quickAuthor}
                onChange={(e) => setQuickAuthor(e.target.value)}
                placeholder="Autor (opțional)..."
                className="flex-1 bg-white/[0.03] border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-white placeholder:text-zinc-500 outline-none focus:border-indigo-400/40 transition-all"
              />
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowAdd(false)}
                className="px-3 py-1 text-xs text-zinc-400 hover:text-white"
              >
                Anulează
              </button>
              <button
                onClick={handleCreate}
                disabled={!quickTitle.trim() || addMut.isPending}
                className="px-3.5 py-1 rounded-xl bg-gradient-to-tr from-primary to-accent text-xs font-bold text-white shadow-sm disabled:opacity-40"
              >
                Adaugă
              </button>
            </div>
          </motion.div>
        ) : (
          <div className="flex justify-end pt-1">
            <button
              onClick={() => setShowAdd(true)}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" /> Adaugă altă carte
            </button>
          </div>
        )}
      </AnimatePresence>
    </WidgetCard>
  )
}
