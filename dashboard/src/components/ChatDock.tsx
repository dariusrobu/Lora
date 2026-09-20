import { useState } from "react"
import { MessageCircle, Send, X } from "lucide-react"
import { api } from "../api/client"

type Message = { role: "user" | "assistant"; content: string }

export function ChatDock() {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState("")
  const [sending, setSending] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])

  const send = async () => {
    const message = value.trim()
    if (!message || sending) return
    setValue("")
    setMessages((items) => [...items, { role: "user", content: message }])
    setSending(true)
    try {
      const { data } = await api.post<{ reply: string }>("/api/llm/chat", { message })
      setMessages((items) => [...items, { role: "assistant", content: data.reply }])
    } catch {
      setMessages((items) => [...items, { role: "assistant", content: "Nu pot contacta Lora local acum. Verifică Ollama și API-ul." }])
    } finally { setSending(false) }
  }

  return <>
    {open && <section className="fixed bottom-24 right-4 z-50 w-[min(380px,calc(100vw-2rem))] h-[min(560px,calc(100vh-8rem))] rounded-2xl border border-border bg-bg shadow-2xl flex flex-col overflow-hidden" aria-label="Conversație cu Lora">
      <header className="flex items-center justify-between px-4 py-3 border-b border-border"><div><p className="font-semibold">Lora</p><p className="text-xs text-text-secondary">Conversație locală</p></div><button onClick={() => setOpen(false)} aria-label="Închide"><X size={18} /></button></header>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && <p className="text-sm text-text-secondary p-2">Spune-mi ce ai pe minte sau ce vrei să organizezi.</p>}
        {messages.map((message, index) => <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${message.role === "user" ? "bg-primary text-white" : "bg-surface border border-border"}`}>{message.content}</div></div>)}
        {sending && <p className="text-xs text-text-secondary p-2">Lora gândește local…</p>}
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void send() }} className="p-3 border-t border-border flex gap-2"><input autoFocus={open} value={value} onChange={(event) => setValue(event.target.value)} placeholder="Vorbește cu Lora…" className="min-w-0 flex-1 h-10 rounded-xl bg-surface border border-border px-3 text-sm outline-none focus:border-primary/50" disabled={sending} /><button type="submit" disabled={!value.trim() || sending} className="w-10 h-10 rounded-xl bg-primary text-white flex items-center justify-center disabled:opacity-50" aria-label="Trimite"><Send size={16} /></button></form>
    </section>}
    <button onClick={() => setOpen((current) => !current)} className="fixed bottom-6 right-4 z-50 w-14 h-14 rounded-full bg-primary text-white shadow-lg flex items-center justify-center hover:scale-105 transition-transform" aria-label="Vorbește cu Lora"><MessageCircle size={24} /></button>
  </>
}
