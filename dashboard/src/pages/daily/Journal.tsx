import { useState, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import { ArrowUpRight, Dumbbell, HeartPulse, Plus, Utensils, Wallet } from "lucide-react"
import { createTransaction, fetchFinanceSummary } from "../../api/queries/finance"
import { fetchDailyNutrition } from "../../api/queries/nutrition"
import { fetchWorkoutStats, logWorkout } from "../../api/queries/workout"
import { isUnauthorized } from "./isUnauthorized"
import { LoginRequired } from "./LoginRequired"

const money = (value: number) => new Intl.NumberFormat("ro-RO", { style: "currency", currency: "RON", maximumFractionDigits: 0 }).format(value)

export default function Journal() {
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const finance = useQuery({ queryKey: ["finance", "summary"], queryFn: fetchFinanceSummary })
  const nutrition = useQuery({ queryKey: ["nutrition", "daily"], queryFn: fetchDailyNutrition })
  const workout = useQuery({ queryKey: ["workout"], queryFn: fetchWorkoutStats })
  const [activeForm, setActiveForm] = useState<"expense" | "workout" | null>(() => {
    const action = searchParams.get("action")
    return action === "expense" || action === "workout" ? action : null
  })
  const [amount, setAmount] = useState("")
  const [description, setDescription] = useState("")
  const [category, setCategory] = useState("Mâncare")
  const [sport, setSport] = useState("Gym")
  const [duration, setDuration] = useState("")
  const [notes, setNotes] = useState("")
  const expenseMutation = useMutation({ mutationFn: createTransaction, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["finance"] }); setAmount(""); setDescription(""); setActiveForm(null) } })
  const workoutMutation = useMutation({ mutationFn: logWorkout, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["workout"] }); setDuration(""); setNotes(""); setActiveForm(null) } })
  const submitExpense = (event: FormEvent) => { event.preventDefault(); if (Number(amount) > 0 && description.trim()) expenseMutation.mutate({ amount: Number(amount), description: description.trim(), category, type: "expense" }) }
  const submitWorkout = (event: FormEvent) => { event.preventDefault(); if (Number(duration) > 0) workoutMutation.mutate({ sport_name: sport, duration_min: Number(duration), notes: notes.trim() || undefined }) }
  if (isUnauthorized(finance.error, nutrition.error, workout.error, expenseMutation.error, workoutMutation.error)) return <LoginRequired />

  return <div className="daily-page"><div className="daily-page-heading"><div><p className="daily-eyebrow">CE AI FĂCUT</p><h1>Jurnal</h1><p className="daily-subtitle">Cheltuieli, mese, antrenamente și sănătate într-un singur loc.</p></div></div>
    <div className="daily-journal-grid">
      <section className="daily-panel daily-journal-section"><div className="daily-journal-title"><span className="daily-journal-icon"><Wallet size={22} /></span><span><h2>Cheltuieli</h2><small>Luna aceasta</small></span><Link to="/finance" aria-label="Deschide finanțele"><ArrowUpRight size={19} /></Link></div>{finance.isPending ? <p className="daily-state">Se încarcă…</p> : finance.isError ? <p className="daily-state daily-error">Datele nu sunt disponibile. <button type="button" onClick={() => finance.refetch()}>Reîncearcă</button></p> : <p className="daily-journal-value">{money(finance.data?.summary.expense ?? 0)}</p>}<button type="button" className="daily-text-button" onClick={() => setActiveForm(activeForm === "expense" ? null : "expense")}><Plus size={15} /> Adaugă cheltuială</button>
        {activeForm === "expense" && <form className="daily-journal-form" onSubmit={submitExpense}><div className="daily-form-grid"><label className="daily-field"><span>Sumă (lei)</span><input type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} required /></label><label className="daily-field"><span>Categorie</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option>Mâncare</option><option>Transport</option><option>Cumpărături</option><option>Altele</option></select></label></div><label className="daily-field"><span>Pe ce ai cheltuit?</span><input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Ex. Prânz la cantină" required /></label>{expenseMutation.isError && <p className="daily-inline-error">Cheltuiala nu a putut fi salvată.</p>}<button type="submit" className="daily-primary-button" disabled={expenseMutation.isPending || Number(amount) <= 0 || !description.trim()}>{expenseMutation.isPending ? "Se salvează…" : "Salvează"}</button></form>}
      </section>
      <section className="daily-panel daily-journal-section"><div className="daily-journal-title"><span className="daily-journal-icon"><Utensils size={22} /></span><span><h2>Mese</h2><small>Astăzi</small></span><Link to="/nutrition" aria-label="Deschide mesele"><ArrowUpRight size={19} /></Link></div>{nutrition.isPending ? <p className="daily-state">Se încarcă…</p> : nutrition.isError ? <p className="daily-state daily-error">Mesele nu sunt disponibile. <button type="button" onClick={() => nutrition.refetch()}>Reîncearcă</button></p> : <><p className="daily-journal-value">{nutrition.data?.meals.length ?? 0} <span>{nutrition.data?.meals.length === 1 ? "masă" : "mese"}</span></p><p className="daily-journal-caption">{nutrition.data?.totals.calories ?? 0} kcal înregistrate</p></>}<Link className="daily-text-button" to="/nutrition">Vezi detaliile și estimările <ArrowUpRight size={14} /></Link></section>
      <section className="daily-panel daily-journal-section"><div className="daily-journal-title"><span className="daily-journal-icon"><Dumbbell size={22} /></span><span><h2>Antrenamente</h2><small>Ultimele 30 de zile</small></span><Link to="/workout" aria-label="Deschide antrenamentele"><ArrowUpRight size={19} /></Link></div>{workout.isPending ? <p className="daily-state">Se încarcă…</p> : workout.isError ? <p className="daily-state daily-error">Antrenamentele nu sunt disponibile. <button type="button" onClick={() => workout.refetch()}>Reîncearcă</button></p> : <p className="daily-journal-value">{workout.data?.stats.total_sessions ?? 0} <span>sesiuni</span></p>}<button type="button" className="daily-text-button" onClick={() => setActiveForm(activeForm === "workout" ? null : "workout")}><Plus size={15} /> Adaugă antrenament</button>
        {activeForm === "workout" && <form className="daily-journal-form" onSubmit={submitWorkout}><div className="daily-form-grid"><label className="daily-field"><span>Activitate</span><select value={sport} onChange={(event) => setSport(event.target.value)}><option>Gym</option><option>Fotbal</option><option>Alergare</option><option>Ciclism</option><option>Yoga</option></select></label><label className="daily-field"><span>Minute</span><input type="number" min="1" max="1440" value={duration} onChange={(event) => setDuration(event.target.value)} required /></label></div><label className="daily-field"><span>Detalii (opțional)</span><input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Ex. Piept" /></label>{workoutMutation.isError && <p className="daily-inline-error">Antrenamentul nu a putut fi salvat.</p>}<button type="submit" className="daily-primary-button" disabled={workoutMutation.isPending || Number(duration) <= 0}>{workoutMutation.isPending ? "Se salvează…" : "Salvează"}</button></form>}
      </section>
      <Link className="daily-panel daily-journal-card" to="/health"><span className="daily-journal-icon"><HeartPulse size={23} /></span><span><strong>Sănătate</strong><small>Somn, apă și măsurători</small></span><ArrowUpRight size={19} /></Link>
    </div>
  </div>
}
