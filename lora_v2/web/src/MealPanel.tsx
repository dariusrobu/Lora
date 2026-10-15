import { useState } from "react"
import { ChevronDown, Pencil, Plus, Sparkles, Trash2 } from "lucide-react"
import { api, type Meal, type MealDetail } from "./api"

type Props = {
  meals: Meal[]
  onAdd: () => void
  onEdit: (id: string) => void
  onRemove: (id: string, version: number) => void
}

const number = (value: number) => new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 1 }).format(value)
const day = (value: string) => new Date(value).toLocaleDateString("ro-RO", { day: "numeric", month: "long" })
function sourceUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return url.protocol === "https:" && ["fdc.nal.usda.gov", "world.openfoodfacts.org"].includes(url.hostname) ? value : undefined
  } catch { return undefined }
}

export default function MealPanel({ meals, onAdd, onEdit, onRemove }: Props) {
  const [open, setOpen] = useState<MealDetail | null>(null)
  const [error, setError] = useState("")
  const [loadingId, setLoadingId] = useState<string | null>(null)

  async function toggle(id: string) {
    if (open?.id === id) { setOpen(null); return }
    setLoadingId(id); setError("")
    try { setOpen(await api.meal(id)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Nu pot încărca masa.") }
    finally { setLoadingId(null) }
  }

  return <section className="glass section-card"><div className="section-title"><Sparkles size={19} /><h2>Mese</h2></div>
    {error && <p className="error" role="alert">{error}</p>}
    {meals.length ? meals.slice(0, 8).map(meal => <div className="meal-list-item" key={meal.id}>
      <div className="simple-row"><span><strong>{meal.description || "Masă"}</strong><small>{day(meal.eaten_at)} · {meal.calories == null ? "nutriție incompletă" : `≈ ${number(meal.calories)} kcal · P ${number(meal.protein_g || 0)} · C ${number(meal.carbs_g || 0)} · G ${number(meal.fat_g || 0)} g`}</small></span>
        <span className="row-actions"><button aria-label={`Detalii pentru ${meal.description || "masă"}`} aria-expanded={open?.id === meal.id} onClick={() => void toggle(meal.id)} disabled={loadingId === meal.id}><ChevronDown size={15} /></button><button aria-label="Editează masa" onClick={() => onEdit(meal.id)}><Pencil size={15} /></button><button aria-label="Șterge masa" onClick={() => onRemove(meal.id, meal.version)}><Trash2 size={15} /></button></span>
      </div>
      {open?.id === meal.id && <div className="meal-detail"><p className="helper">Valorile sunt estimate pentru gramajul înregistrat.</p>{open.items.map(item => <div className="meal-detail-item" key={item.id}><strong>{item.name}</strong><small>{item.grams != null ? `${number(item.grams)} g` : "Gramaj necunoscut"} · {item.calories != null ? `${number(item.calories)} kcal · P ${number(item.protein_g || 0)} · C ${number(item.carbs_g || 0)} · G ${number(item.fat_g || 0)} g` : "fără macro-uri verificate"}</small>{item.nutrition_provider && <small>{sourceUrl(item.nutrition_source_url) ? <a href={sourceUrl(item.nutrition_source_url)} target="_blank" rel="noopener noreferrer">{item.nutrition_provider} · {item.nutrition_source_title}</a> : `${item.nutrition_provider} · ${item.nutrition_source_title}`}</small>}</div>)}</div>}
    </div>) : <p className="empty">Nicio masă încă.</p>}
    <button className="text-action" onClick={onAdd}><Plus size={15} /> Adaugă masă</button>
  </section>
}
