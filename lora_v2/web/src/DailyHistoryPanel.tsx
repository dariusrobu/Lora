import { useCallback, useEffect, useState } from "react"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { api, type DailyHistory, type DayPlan, type ExpenseCategory, type Reflection } from "./api"

type Editor = { kind: "reflection" | "plan" | "category"; id?: string; version?: number }
type Fields = Record<string, string>
const today = () => new Date().toLocaleDateString("en-CA")

export default function DailyHistoryPanel() {
  const [data, setData] = useState<DailyHistory | null>(null)
  const [editor, setEditor] = useState<Editor | null>(null)
  const [fields, setFields] = useState<Fields>({})
  const [expanded, setExpanded] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const load = useCallback(async () => setData(await api.dailyHistory()), [])
  useEffect(() => { void load().catch(() => setError("Nu am putut încărca istoricul.")) }, [load])

  function openReflection(item?: Reflection) {
    setEditor({ kind: "reflection", id: item?.id, version: item?.version })
    setFields({ date: item?.entry_date || today(), text: item?.reflection_text || "", mood: item?.mood || "", focus: item?.tomorrow_focus || "", completion: item?.task_completion || "" })
  }

  function openPlan(item?: DayPlan) {
    setEditor({ kind: "plan", id: item?.id, version: item?.version })
    setFields({ date: item?.plan_date || today(), input: item?.user_input || "", itinerary: item?.itinerary || "", wake: item?.wake_time?.slice(0, 5) || "" })
  }

  function openCategory(item?: ExpenseCategory) {
    setEditor({ kind: "category", id: item?.id, version: item?.version })
    setFields({ name: item?.name || "", icon: item?.icon || "", keywords: item?.keywords.join(", ") || "" })
  }

  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!editor) return
    setBusy(true); setError("")
    try {
      if (editor.kind === "reflection") {
        const body = { entry_date: fields.date, reflection_text: fields.text || null, mood: fields.mood || null, tomorrow_focus: fields.focus || null, task_completion: fields.completion || null, expected_version: editor.version }
        if (editor.id) await api.editReflection(editor.id, body)
        else await api.createReflection(body)
      } else if (editor.kind === "plan") {
        const body = { plan_date: fields.date, user_input: fields.input || null, itinerary: fields.itinerary || null, wake_time: fields.wake || null, expected_version: editor.version }
        if (editor.id) await api.editPlan(editor.id, body)
        else await api.createPlan(body)
      } else {
        const body = { name: fields.name.trim(), icon: fields.icon || null, keywords: fields.keywords.split(",").map(word => word.trim()).filter(Boolean), is_active: true, expected_version: editor.version }
        if (editor.id) await api.editExpenseCategory(editor.id, body)
        else await api.createExpenseCategory(body)
      }
      setEditor(null); await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva.") }
    finally { setBusy(false) }
  }

  async function remove(kind: Editor["kind"], id: string, version: number) {
    if (!window.confirm("Ștergi acest element?")) return
    setBusy(true); setError("")
    try {
      if (kind === "reflection") await api.deleteReflection(id, version)
      else if (kind === "plan") await api.deletePlan(id, version)
      else await api.deleteExpenseCategory(id, version)
      await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut șterge.") }
    finally { setBusy(false) }
  }

  async function saveTargets(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("")
    const form = new FormData(event.currentTarget)
    const number = (key: string) => form.get(key) ? Number(form.get(key)) : null
    try {
      await api.saveNutritionTargets({ calories: number("calories"), protein_g: number("protein_g"), carbs_g: number("carbs_g"), fat_g: number("fat_g"), expected_version: data?.nutrition_targets?.version ?? null })
      await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva țintele.") }
    finally { setBusy(false) }
  }

  async function savePreferences(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("")
    const form = new FormData(event.currentTarget)
    const current = data?.preferences?.data || {}
    const updated = { ...current, faculty: String(form.get("faculty") || ""), study_group: String(form.get("study_group") || ""), dietary_preferences: String(form.get("dietary_preferences") || ""), water_target_ml: form.get("water_target_ml") ? Number(form.get("water_target_ml")) : null }
    try {
      await api.savePreferences(updated, data?.preferences?.version ?? null)
      await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva preferințele.") }
    finally { setBusy(false) }
  }

  const reflections = expanded ? data?.reflections || [] : data?.reflections.slice(0, 5) || []
  const plans = expanded ? data?.plans || [] : data?.plans.slice(0, 5) || []

  return <details className="glass section-card daily-history"><summary>Istoric și preferințe</summary>
    {error && <p className="error" role="alert">{error}</p>}
    {!data ? <p className="empty">Se încarcă…</p> : <>
      <h3>Reflecții</h3>
      {reflections.length ? reflections.map(item => <div className="simple-row" key={item.id}><span><strong>{item.entry_date}</strong><small>{item.reflection_text || item.mood || (item.skipped ? "Zi sărită" : "Fără text")}</small></span><span className="row-actions"><button aria-label="Editează reflecția" onClick={() => openReflection(item)}><Pencil size={14} /></button><button aria-label="Șterge reflecția" onClick={() => void remove("reflection", item.id, item.version)}><Trash2 size={14} /></button></span></div>) : <p className="empty">Nicio reflecție.</p>}
      <button className="text-action" onClick={() => openReflection()}><Plus size={14} /> Reflecție</button>

      <h3>Planuri zilnice</h3>
      {plans.length ? plans.map(item => <div className="simple-row" key={item.id}><span><strong>{item.plan_date}</strong><small>{item.itinerary || item.user_input || "Fără descriere"}</small></span><span className="row-actions"><button aria-label="Editează planul" onClick={() => openPlan(item)}><Pencil size={14} /></button><button aria-label="Șterge planul" onClick={() => void remove("plan", item.id, item.version)}><Trash2 size={14} /></button></span></div>) : <p className="empty">Niciun plan.</p>}
      <button className="text-action" onClick={() => openPlan()}><Plus size={14} /> Plan</button>
      {((data.reflections.length > 5) || (data.plans.length > 5)) && <button className="text-action" onClick={() => setExpanded(!expanded)}>{expanded ? "Arată mai puține" : "Vezi tot istoricul"}</button>}

      <h3>Categorii de cheltuieli</h3>
      {data.categories.filter(item => item.is_active).map(item => <div className="simple-row" key={item.id}><span><strong>{item.icon} {item.name}</strong><small>{item.keywords.join(", ")}</small></span><span className="row-actions"><button aria-label={`Editează ${item.name}`} onClick={() => openCategory(item)}><Pencil size={14} /></button><button aria-label={`Dezactivează ${item.name}`} onClick={() => void remove("category", item.id, item.version)}><Trash2 size={14} /></button></span></div>)}
      <button className="text-action" onClick={() => openCategory()}><Plus size={14} /> Categorie</button>

      {editor && <form className="history-form" onSubmit={event => void save(event)}>
        <strong>{editor.id ? "Editează" : "Adaugă"} {editor.kind === "reflection" ? "reflecție" : editor.kind === "plan" ? "plan" : "categorie"}</strong>
        {editor.kind !== "category" && <label>Data<input type="date" required value={fields.date} onChange={event => setFields({ ...fields, date: event.target.value })} /></label>}
        {editor.kind === "reflection" && <><label>Reflecție<textarea value={fields.text} onChange={event => setFields({ ...fields, text: event.target.value })} /></label><label>Stare<input value={fields.mood} onChange={event => setFields({ ...fields, mood: event.target.value })} /></label><label>Mâine contează<input value={fields.focus} onChange={event => setFields({ ...fields, focus: event.target.value })} /></label></>}
        {editor.kind === "plan" && <><label>Ce ai în plan<textarea value={fields.input} onChange={event => setFields({ ...fields, input: event.target.value })} /></label><label>Program<textarea value={fields.itinerary} onChange={event => setFields({ ...fields, itinerary: event.target.value })} /></label><label>Ora trezirii<input type="time" value={fields.wake} onChange={event => setFields({ ...fields, wake: event.target.value })} /></label></>}
        {editor.kind === "category" && <><label>Categorie<input required value={fields.name} onChange={event => setFields({ ...fields, name: event.target.value })} /></label><label>Icon<input value={fields.icon} onChange={event => setFields({ ...fields, icon: event.target.value })} /></label><label>Cuvinte asociate, separate prin virgulă<input value={fields.keywords} onChange={event => setFields({ ...fields, keywords: event.target.value })} /></label></>}
        <div className="inline-actions"><button type="submit" disabled={busy}>Salvează</button><button type="button" onClick={() => setEditor(null)}>Anulează</button></div>
      </form>}

      <details className="history-subsection"><summary>Ținte nutriționale</summary><form className="history-form" onSubmit={event => void saveTargets(event)} key={data.nutrition_targets?.version || 0}><label>Calorii<input name="calories" type="number" min="0" defaultValue={data.nutrition_targets?.calories ?? ""} /></label><label>Proteine g<input name="protein_g" type="number" min="0" defaultValue={data.nutrition_targets?.protein_g ?? ""} /></label><label>Carbohidrați g<input name="carbs_g" type="number" min="0" defaultValue={data.nutrition_targets?.carbs_g ?? ""} /></label><label>Grăsimi g<input name="fat_g" type="number" min="0" defaultValue={data.nutrition_targets?.fat_g ?? ""} /></label><button className="primary" type="submit" disabled={busy}>Salvează</button></form></details>
      <details className="history-subsection"><summary>Preferințe</summary><form className="history-form" onSubmit={event => void savePreferences(event)} key={data.preferences?.version || 0}><label>Facultate<input name="faculty" defaultValue={String(data.preferences?.data.faculty || "")} /></label><label>Grupă<input name="study_group" defaultValue={String(data.preferences?.data.study_group || "")} /></label><label>Alimentație<input name="dietary_preferences" defaultValue={String(data.preferences?.data.dietary_preferences || "")} /></label><label>Țintă apă, ml<input name="water_target_ml" type="number" min="0" defaultValue={String(data.preferences?.data.water_target_ml || "")} /></label><button className="primary" type="submit" disabled={busy}>Salvează</button></form></details>
    </>}
  </details>
}
