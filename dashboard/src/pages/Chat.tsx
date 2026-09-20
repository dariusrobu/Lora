import { useState } from "react"
import { Send, Sparkles } from "lucide-react"
import { api } from "../api/client"

type Message = { role: "user" | "assistant"; content: string }

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [value, setValue] = useState("")
  const [sending, setSending] = useState(false)

  const send = async () => {
    const message = value.trim()
    if (!message || sending) return
    setValue("")
    setMessages((current) => [...current, { role: "user", content: message }])
    setSending(true)
    try {
      const response = await api.post<{ reply: string; requires_confirmation: boolean }>("/api/llm/chat", { message })
      setMessages((current) => [...current, { role: "assistant", content: response.data.reply }])
    } catch {
      setMessages((current) => [...current, { role: "assistant", content: "Nu am putut contacta Lora local. Verifică Ollama și API-ul." }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-2xl bg-primary/15 flex items-center justify-center"><Sparkles size={20} className="text-primary" /></div>
        <div><h1 className="text-2xl font-semibold">Vorbește cu Lora</h1><p className="text-sm text-text-secondary">Conversație locală prin Ollama</p></div>
      </div>
      <div className="min-h-[55vh] rounded-2xl border border-border bg-surface/60 p-4 space-y-3">
        {messages.length === 0 && <p className="text-text-secondary text-sm">Poți întreba despre ziua ta, task-uri, finanțe sau orice vrei să clarifici.</p>}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 whitespace-pre-wrap text-sm ${message.role === "user" ? "bg-primary text-white" : "bg-surface border border-border"}`}>
              {message.content}
            </div>
          </div>
        ))}
        {sending && <p className="text-xs text-text-secondary">Lora gândește local…</p>}
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void send() }} className="flex gap-2">
        <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="Scrie-i Lora…" className="flex-1 h-12 rounded-xl bg-surface border border-border px-4 outline-none focus:border-primary/50" disabled={sending} />
        <button type="submit" className="w-12 h-12 rounded-xl bg-primary text-white flex items-center justify-center disabled:opacity-50" disabled={!value.trim() || sending} aria-label="Trimite"><Send size={18} /></button>
      </form>
    </div>
  )
}
