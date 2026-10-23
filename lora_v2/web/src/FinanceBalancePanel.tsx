import { useState } from "react"
import { Wallet, X } from "lucide-react"
import { api, type FinanceBalance } from "./api"

const money = (amount: number) => new Intl.NumberFormat("ro-RO", {
  style: "currency", currency: "RON", maximumFractionDigits: 2,
}).format(amount)

export default function FinanceBalancePanel({ balance, onChange }: {
  balance: FinanceBalance | null
  onChange: () => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [amount, setAmount] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function save(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true); setError("")
    try {
      await api.setFinanceBalance(amount, balance?.version ?? null)
      setEditing(false); setAmount("")
      await onChange()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Nu am putut salva soldul.")
    } finally { setBusy(false) }
  }

  async function clear() {
    if (balance?.version == null || !window.confirm("Elimini soldul urmărit? Tranzacțiile rămân salvate.")) return
    setBusy(true); setError("")
    try {
      await api.clearFinanceBalance(balance.version)
      setEditing(false); await onChange()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Nu am putut elimina soldul.")
    } finally { setBusy(false) }
  }

  return <section className="glass section-card finance-balance-panel">
    <div className="section-title"><Wallet size={19} /><h2>Sold</h2></div>
    {balance?.balance != null ? <>
      <strong className="finance-balance-value">{money(balance.balance)}</strong>
      <p className="helper">Estimat din soldul introdus de tine și tranzacțiile înregistrate după {balance.as_of ? new Date(balance.as_of).toLocaleString("ro-RO", { dateStyle: "short", timeStyle: "short" }) : "ultima actualizare"}. Nu este conectat la bancă.</p>
    </> : <p className="helper">Ca să știi cât ai acum, introdu soldul real în lei. Tranzacțiile vechi rămân în istoric și nu sunt scăzute încă o dată.</p>}
    {error && <p className="daily-inline-error" role="alert">{error}</p>}
    {!editing ? <div className="finance-balance-actions">
      <button type="button" className="text-action" onClick={() => { setAmount(""); setError(""); setEditing(true) }}>{balance?.balance == null ? "Setează soldul de acum" : "Corectează soldul"}</button>
      {balance?.version != null && <button type="button" className="text-action finance-clear" disabled={busy} onClick={() => void clear()}>Elimină soldul</button>}
    </div> : <form className="finance-balance-form" onSubmit={event => void save(event)}>
      <label>Soldul real acum, în lei<input autoFocus type="number" min="0" step="0.01" inputMode="decimal" required value={amount} onChange={event => setAmount(event.target.value)} /></label>
      <div className="finance-balance-actions"><button type="submit" className="primary" disabled={busy || amount === ""}>{busy ? "Se salvează…" : "Salvează soldul"}</button><button type="button" className="close-form" aria-label="Anulează" onClick={() => setEditing(false)}><X size={17} /></button></div>
    </form>}
  </section>
}
