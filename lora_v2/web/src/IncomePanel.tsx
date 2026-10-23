import { useCallback, useEffect, useState } from "react"
import { Pencil, Plus, Trash2, Wallet, X } from "lucide-react"
import { api, type Income } from "./api"

const localInput = (value: string) => {
  const date = new Date(value)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}T${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`
}

export default function IncomePanel({ onChange }: { onChange: () => Promise<void> }) {
  const [incomes, setIncomes] = useState<Income[]>([])
  const [form, setForm] = useState<{ id?: string; version?: number } | null>(null)
  const [fields, setFields] = useState({ amount: "", category: "", source: "", description: "", at: "" })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const reload = useCallback(async () => setIncomes((await api.journal()).incomes), [])
  useEffect(() => { void reload().catch(cause => setError(cause instanceof Error ? cause.message : "Nu am putut încărca veniturile.")) }, [reload])

  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("")
    const data = {
      amount: fields.amount, currency: "RON", category: fields.category || null,
      source: fields.source || null, description: fields.description || null,
      received_at: new Date(fields.at || Date.now()).toISOString(),
    }
    try {
      if (form?.id && form.version) await api.edit("income", form.id, form.version, data)
      else await api.action("log_income", data)
      setForm(null); await Promise.all([reload(), onChange()])
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva venitul.") }
    finally { setBusy(false) }
  }

  async function remove(item: Income) {
    if (!window.confirm("Ștergi acest venit?")) return
    setBusy(true); setError("")
    try { await api.remove("income", item.id, item.version); await Promise.all([reload(), onChange()]) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut șterge venitul.") }
    finally { setBusy(false) }
  }

  return <section className="glass section-card income-panel"><div className="section-title"><Wallet size={19} /><h2>Venituri</h2></div>
    {error && <div className="error" role="alert">{error}</div>}
    {incomes.length ? incomes.slice(0, 12).map(item => <div className="simple-row" key={item.id}><span><strong>{item.source || item.description || item.category || "Venit"}</strong><small>{new Date(item.received_at).toLocaleDateString("ro-RO")}</small></span><b>+{item.amount} {item.currency}</b><span className="row-actions"><button aria-label="Editează venit" onClick={() => { setForm({ id: item.id, version: item.version }); setFields({ amount: String(item.amount), category: item.category || "", source: item.source || "", description: item.description || "", at: localInput(item.received_at) }) }}><Pencil size={14} /></button><button aria-label="Șterge venit" onClick={() => void remove(item)}><Trash2 size={14} /></button></span></div>) : <p className="empty">Niciun venit înregistrat.</p>}
    {!form ? <button className="text-action" onClick={() => { setFields({ amount: "", category: "", source: "", description: "", at: localInput(new Date().toISOString()) }); setForm({}) }}><Plus size={15} /> Adaugă venit</button> : <form className="income-form" onSubmit={event => void save(event)}><div className="section-title"><h3>{form.id ? "Editează venit" : "Venit nou"}</h3><button type="button" className="close-form" onClick={() => setForm(null)} aria-label="Închide"><X size={16} /></button></div><label>Sumă (lei)<input type="number" min="0.01" step="0.01" required value={fields.amount} onChange={event => setFields({ ...fields, amount: event.target.value })} /></label><label>Sursă<input value={fields.source} onChange={event => setFields({ ...fields, source: event.target.value })} /></label><label>Categorie<input value={fields.category} onChange={event => setFields({ ...fields, category: event.target.value })} /></label><label>Descriere<input value={fields.description} onChange={event => setFields({ ...fields, description: event.target.value })} /></label><label>Data<input type="datetime-local" required value={fields.at} onChange={event => setFields({ ...fields, at: event.target.value })} /></label><button className="primary" type="submit" disabled={busy}>Salvează</button></form>}
  </section>
}
