import { useEffect, useState } from "react"
import { FileText, Pencil, Plus, Trash2, X } from "lucide-react"
import { api, type UniversityNote, type UniversityRecord } from "./api"

type Draft = { id?: string; version?: number; title: string; body: string; subject_id: string }

export default function UniversityNotes({ subjects }: { subjects: UniversityRecord[] }) {
  const [notes, setNotes] = useState<UniversityNote[]>([])
  const [filter, setFilter] = useState("")
  const [draft, setDraft] = useState<Draft | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function reload() { setNotes(await api.universityNotes()) }
  useEffect(() => { void reload().catch(cause => setError(cause instanceof Error ? cause.message : "Nu pot încărca notițele.")) }, [])

  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!draft?.title.trim()) return
    setBusy(true); setError("")
    try {
      if (draft.id && draft.version) await api.editUniversityNote(draft.id, draft.title, draft.body, draft.subject_id || null, draft.version)
      else await api.createUniversityNote(draft.title, draft.body, draft.subject_id || null)
      setDraft(null)
      await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut salva notița.") }
    finally { setBusy(false) }
  }

  async function remove(note: UniversityNote) {
    if (!window.confirm(`Ștergi notița „${note.title}”?`)) return
    setBusy(true); setError("")
    try { await api.deleteUniversityNote(note.id, note.version); await reload() }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Nu am putut șterge notița.") }
    finally { setBusy(false) }
  }

  const visible = notes.filter(note => !filter || note.subject_id === filter)
  return <section className="glass section-card university-notes">
    <div className="section-title"><FileText size={19} /><h2>Notițe</h2><button className="notes-add" type="button" onClick={() => setDraft({ title: "", body: "", subject_id: filter })}><Plus size={16} /> Adaugă</button></div>
    {error && <p className="error" role="alert">{error}</p>}
    <label className="notes-filter">Materie<select value={filter} onChange={event => setFilter(event.target.value)}><option value="">Toate</option>{subjects.map(subject => <option key={subject.id} value={subject.id}>{String(subject.name)}</option>)}</select></label>
    {draft && <form className="inline-form notes-form" onSubmit={event => void save(event)}>
      <div className="section-title"><h2>{draft.id ? "Editează notița" : "Notiță nouă"}</h2><button type="button" className="close-form" onClick={() => setDraft(null)} aria-label="Închide"><X size={17} /></button></div>
      <label>Titlu<input autoFocus required maxLength={240} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} /></label>
      <label>Materie<select value={draft.subject_id} onChange={event => setDraft({ ...draft, subject_id: event.target.value })}><option value="">Fără materie</option>{subjects.map(subject => <option key={subject.id} value={subject.id}>{String(subject.name)}</option>)}</select></label>
      <label>Conținut<textarea value={draft.body} onChange={event => setDraft({ ...draft, body: event.target.value })} rows={10} maxLength={200000} placeholder="Scrie aici…" /></label>
      <button className="primary" disabled={busy} type="submit">Salvează</button>
    </form>}
    {visible.length ? <div className="notes-list">{visible.map(note => <details key={note.id} className="note-item"><summary><span><strong>{note.title}</strong><small>{note.subject_name || "Fără materie"}</small></span></summary><div className="note-body"><p>{note.body || "Notița este goală."}</p><div className="inline-actions"><button type="button" onClick={() => setDraft({ id: note.id, version: note.version, title: note.title, body: note.body, subject_id: note.subject_id || "" })}><Pencil size={15} /> Editează</button><button type="button" disabled={busy} onClick={() => void remove(note)}><Trash2 size={15} /> Șterge</button></div></div></details>)}</div> : <p className="empty">Nu ai notițe aici încă.</p>}
  </section>
}
