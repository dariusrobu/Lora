import { useState } from "react"
import { api, type Proposal, type ReceiptLineDraft } from "./api"

type LocalLine = ReceiptLineDraft & { key: string }

function draftFrom(proposal: Proposal): { merchant: string; total: string; items: LocalLine[] } {
  const data = proposal.command.data
  const source = Array.isArray(data.items) ? data.items : []
  return {
    merchant: String(data.merchant || ""), total: String(data.total_amount || ""),
    items: source.map(raw => {
      const item = raw as Record<string, unknown>
      return { key: crypto.randomUUID(), name: String(item.name || ""), amount: String(item.amount || ""),
        category: String(item.category || ""), category_uncertain: Boolean(item.category_uncertain) }
    }),
  }
}

type Props = {
  proposal: Proposal
  busy: boolean
  onChanged: () => Promise<void>
  onDecision: (accept: boolean) => void
}

export default function ReceiptReview({ proposal, busy, onChanged, onDecision }: Props) {
  const [initial] = useState(() => draftFrom(proposal))
  const [merchant, setMerchant] = useState(initial.merchant)
  const [total, setTotal] = useState(initial.total)
  const [items, setItems] = useState<LocalLine[]>(initial.items)
  const [version, setVersion] = useState(proposal.version)
  const [saved, setSaved] = useState(!initial.items.some(item => item.category_uncertain))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const sum = items.reduce((value, item) => value + Number(item.amount.replace(",", ".")), 0)
  const reconciled = Number.isFinite(sum) && Number.isFinite(Number(total.replace(",", ".")))
    && Math.abs(sum - Number(total.replace(",", "."))) <= 0.05
  const ready = items.length > 0 && items.every(item => item.name.trim() && item.category.trim() && Number(item.amount.replace(",", ".")) > 0)

  function changeItem(index: number, key: keyof ReceiptLineDraft, value: string) {
    setSaved(false)
    setItems(current => current.map((item, position) => position === index ? { ...item, [key]: value } : item))
  }

  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!ready || !reconciled) return
    setSaving(true); setError("")
    try {
      const result = await api.editReceiptProposal(proposal.id, version, merchant.trim(), total.replace(",", "."),
        items.map(item => ({ ...item, amount: item.amount.replace(",", "."), category_uncertain: false })))
      setVersion(result.version)
      setItems(current => current.map(item => ({ ...item, category_uncertain: false })))
      setSaved(true)
      await onChanged()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut corecta bonul.") }
    finally { setSaving(false) }
  }

  return <div className="proposal-row receipt-review">
    <h3>Bon de verificat</h3>
    <p>Verifică fiecare produs. Nu salvăm nimic până nu confirmi.</p>
    <form onSubmit={event => void save(event)}>
      <label>Comerciant<input value={merchant} onChange={event => { setMerchant(event.target.value); setSaved(false) }} placeholder="Magazin" /></label>
      <div className="receipt-lines">{items.map((item, index) => <div className="receipt-line" key={item.key}>
        <label>Produs<input value={item.name} onChange={event => changeItem(index, "name", event.target.value)} required /></label>
        <label>Lei<input value={item.amount} onChange={event => changeItem(index, "amount", event.target.value)} inputMode="decimal" required /></label>
        <label>Categoria{item.category_uncertain ? <span className="receipt-uncertain"> · de ales</span> : null}
          <input value={item.category} onChange={event => changeItem(index, "category", event.target.value)} required /></label>
        <button type="button" className="text-action" onClick={() => { setItems(current => current.filter((_, position) => position !== index)); setSaved(false) }} aria-label={`Șterge produsul ${item.name || index + 1}`}>Șterge</button>
      </div>)}</div>
      <button type="button" className="text-action" onClick={() => { setItems(current => [...current, { key: crypto.randomUUID(), name: "", amount: "", category: "" }]); setSaved(false) }}>+ Adaugă produs</button>
      <label>Total bon (lei)<input value={total} onChange={event => { setTotal(event.target.value); setSaved(false) }} inputMode="decimal" required /></label>
      <p className={reconciled ? "receipt-total-ok" : "receipt-total-error"}>Suma produselor: {sum.toFixed(2)} lei{reconciled ? " · corespunde" : " · nu corespunde totalului"}</p>
      {error ? <p className="receipt-total-error" role="alert">{error}</p> : null}
      <div className="inline-actions"><button type="submit" disabled={busy || saving || !ready || !reconciled}>Salvează corecturile</button>
        <button type="button" disabled={busy || saving || !saved} onClick={() => onDecision(true)}>Confirmă bonul</button>
        <button type="button" disabled={busy || saving} onClick={() => onDecision(false)}>Renunță</button></div>
    </form>
  </div>
}
