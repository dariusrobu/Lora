import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ArrowRight, Command, Search, X } from "lucide-react"

interface Props { open: boolean; onClose: () => void }

const items = [
  { label: "Azi", hint: "Ce urmează și ce ai de făcut", path: "/" },
  { label: "Adaugă task", hint: "Alege proiectul și termenul", path: "/projects?action=task" },
  { label: "Adaugă cheltuială", hint: "Înregistrează o tranzacție", path: "/finance?action=add" },
  { label: "Adaugă reminder", hint: "Alege ora la care să fii anunțat", path: "/calendar?action=reminder" },
  { label: "Adaugă eveniment", hint: "Planifică un moment în calendar", path: "/calendar?action=event" },
  { label: "Calendar", hint: "Evenimente, remindere și orar", path: "/calendar" },
  { label: "Proiecte și taskuri", hint: "Lucruri de făcut, grupate pe proiecte", path: "/projects" },
  { label: "Jurnal", hint: "Cheltuieli, mese, antrenamente și sănătate", path: "/journal" },
  { label: "Facultate", hint: "Materii, note și prezențe", path: "/university" },
  { label: "Vorbește cu Lora", hint: "Conversație", path: "/chat" },
]

export function CommandPalette({ open, onClose }: Props) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const filtered = useMemo(() => items.filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(query.toLowerCase())), [query])

  useEffect(() => {
    if (!open) return
    requestAnimationFrame(() => { setQuery(""); setSelectedIndex(0); inputRef.current?.focus() })
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null
  return <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/45 px-4 pt-[10vh] backdrop-blur-sm" onMouseDown={onClose}>
    <div className="w-full max-w-lg overflow-hidden rounded-3xl border border-border bg-surface shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3"><Search className="h-4 w-4 text-text-muted" /><input ref={inputRef} value={query} onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }} onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIndex((index) => Math.min(index + 1, filtered.length - 1)) } if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIndex((index) => Math.max(0, index - 1)) } if (e.key === "Enter" && filtered[selectedIndex]) { navigate(filtered[selectedIndex].path); onClose() } }} placeholder="Caută o pagină sau o acțiune…" className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted" /><kbd className="hidden rounded-md border border-border px-1.5 py-0.5 text-[10px] text-text-muted sm:block">ESC</kbd><button type="button" onClick={onClose} aria-label="Închide"><X className="h-4 w-4 text-text-muted" /></button></div>
      <div className="max-h-[60vh] overflow-y-auto p-2">{filtered.length ? filtered.map((item, index) => <button key={item.path} type="button" onMouseEnter={() => setSelectedIndex(index)} onClick={() => { navigate(item.path); onClose() }} className={`group flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left hover:bg-black/[0.04] dark:hover:bg-white/[0.05] ${selectedIndex === index ? "bg-black/[0.04] dark:bg-white/[0.05]" : ""}`}><div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary"><Command className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-sm font-medium text-text-primary">{item.label}</p><p className="text-xs text-text-muted">{item.hint}</p></div><ArrowRight className="h-4 w-4 text-text-muted opacity-0 transition-opacity group-hover:opacity-100" /></button>) : <p className="px-3 py-8 text-center text-sm text-text-muted">Nu am găsit nimic.</p>}</div>
      <div className="border-t border-border px-4 py-2 text-[10px] text-text-muted">↑ ↓ pentru navigare · Enter pentru deschidere</div>
    </div>
  </div>
}
