import { useState, useEffect, useRef } from "react"
import { motion } from "framer-motion"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "../api/client"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { Spinner } from "../components/ui/Spinner"
import { User, Cpu, Puzzle, Brain, GitBranch, Clock, Sparkles, Timer, ScrollText, RefreshCw, Download, HardDrive } from "lucide-react"
import type { Profile, MemoryFact, JobConfig, LogStats, LogEntry, LogResponse, CalendarSyncStatus, BackupConfig, BackupRecord } from "../types"

const tabs = [
  { key: "profile", label: "Profile", icon: User },
  { key: "llm", label: "LLM", icon: Cpu },
  { key: "integrations", label: "Integrations", icon: Puzzle },
  { key: "lore", label: "Lore", icon: Brain },
  { key: "correlations", label: "Correlations", icon: GitBranch },
  { key: "timeline", label: "Timeline", icon: Clock },
  { key: "auto", label: "Auto-Learning", icon: Sparkles },
  { key: "jobs", label: "Jobs", icon: Timer },
  { key: "logs", label: "Logs", icon: ScrollText },
  { key: "calendar-sync", label: "Calendar Sync", icon: RefreshCw },
  { key: "export", label: "Export", icon: Download },
  { key: "backups", label: "Backups", icon: HardDrive },
] as const

type TabKey = (typeof tabs)[number]["key"]

function ProfileTab({ profile, onUpdate }: { profile: Profile; onUpdate: (data: Partial<Profile>) => Promise<void> }) {
  const [form, setForm] = useState({
    name: profile.name || "",
    tone: profile.tone || "warm",
    preferred_tone: profile.preferred_tone || "",
    timezone: profile.timezone || "Europe/Bucharest",
    morning_time: profile.morning_time || "08:00",
    eod_time: profile.eod_time || "21:00",
    active_hours_start: profile.active_hours_start || "08:00",
    active_hours_end: profile.active_hours_end || "22:00",
    water_target_ml: profile.water_target_ml || 2000,
    personal_notes: profile.personal_notes || "",
    city_name: profile.city_name || "",
    is_at_home: profile.is_at_home ?? true,
    home_latitude: profile.home_latitude ?? undefined as number | undefined,
    home_longitude: profile.home_longitude ?? undefined as number | undefined,
    university_name: profile.university_name || "",
    faculty: profile.faculty || "",
    specialization: profile.specialization || "",
    study_year: profile.study_year ?? undefined as number | undefined,
    study_group: profile.study_group || "",
    units: profile.units || "metric",
    language: profile.language || "ro",
    week_start_day: profile.week_start_day || "monday",
    currency: profile.currency || "RON",
    dietary_preferences: profile.dietary_preferences || "",
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try { await onUpdate(form) } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-3">General</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="Nume" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Ton principal</label>
            <select className="w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
              value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })}>
              <option value="warm">Warm</option>
              <option value="direct">Direct</option>
              <option value="brief">Brief</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Ton preferat (opțional)</label>
            <select className="w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
              value={form.preferred_tone} onChange={(e) => setForm({ ...form, preferred_tone: e.target.value })}>
              <option value="">La fel ca tonul principal</option>
              <option value="formal">Formal</option>
              <option value="casual">Casual</option>
              <option value="direct">Direct</option>
            </select>
          </div>
          <Input label="Timezone" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          <Input label="Morning briefing" type="time" value={form.morning_time} onChange={(e) => setForm({ ...form, morning_time: e.target.value })} />
          <Input label="EOD reflection" type="time" value={form.eod_time} onChange={(e) => setForm({ ...form, eod_time: e.target.value })} />
          <Input label="Active hours start" type="time" value={form.active_hours_start} onChange={(e) => setForm({ ...form, active_hours_start: e.target.value })} />
          <Input label="Active hours end" type="time" value={form.active_hours_end} onChange={(e) => setForm({ ...form, active_hours_end: e.target.value })} />
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-3">Locație</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="Oraș" value={form.city_name} onChange={(e) => setForm({ ...form, city_name: e.target.value })} placeholder="Bucharest" />
          <div className="flex items-center gap-3 pt-2">
            <button onClick={() => setForm({ ...form, is_at_home: !form.is_at_home })}
              className={`w-10 h-6 rounded-full transition-colors ${form.is_at_home ? "bg-emerald-500" : "bg-border"}`}>
              <div className={`w-4 h-4 rounded-full bg-white transition-transform ${form.is_at_home ? "translate-x-5" : "translate-x-0.5"}`} />
            </button>
            <span className="text-sm">{form.is_at_home ? "Acasă" : "Plecat"}</span>
          </div>
          <Input label="Latitudine acasă" type="number" step="any" value={form.home_latitude ?? ""} onChange={(e) => setForm({ ...form, home_latitude: e.target.value ? parseFloat(e.target.value) : undefined })} />
          <Input label="Longitudine acasă" type="number" step="any" value={form.home_longitude ?? ""} onChange={(e) => setForm({ ...form, home_longitude: e.target.value ? parseFloat(e.target.value) : undefined })} />
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-3">Universitate</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="Universitate" value={form.university_name} onChange={(e) => setForm({ ...form, university_name: e.target.value })} />
          <Input label="Facultate" value={form.faculty} onChange={(e) => setForm({ ...form, faculty: e.target.value })} />
          <Input label="Specializare" value={form.specialization} onChange={(e) => setForm({ ...form, specialization: e.target.value })} />
          <Input label="An studiu" type="number" value={form.study_year ?? ""} onChange={(e) => setForm({ ...form, study_year: e.target.value ? parseInt(e.target.value) : undefined })} />
          <Input label="Grupă" value={form.study_group} onChange={(e) => setForm({ ...form, study_group: e.target.value })} />
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-3">Preferințe</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Unități</label>
            <select className="w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
              value={form.units} onChange={(e) => setForm({ ...form, units: e.target.value })}>
              <option value="metric">Metric (kg, km, °C)</option>
              <option value="imperial">Imperial (lbs, miles, °F)</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Limbă</label>
            <select className="w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
              value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
              <option value="ro">Română</option>
              <option value="en">English</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Prima zi a săptămânii</label>
            <select className="w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
              value={form.week_start_day} onChange={(e) => setForm({ ...form, week_start_day: e.target.value })}>
              <option value="monday">Luni</option>
              <option value="sunday">Duminică</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Monedă</label>
            <select className="w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
              value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
              <option value="RON">RON (Lei)</option>
              <option value="EUR">EUR (€)</option>
              <option value="USD">USD ($)</option>
            </select>
          </div>
          <Input label="Preferințe alimentare" value={form.dietary_preferences} onChange={(e) => setForm({ ...form, dietary_preferences: e.target.value })} placeholder="vegetarian, vegan, etc." />
          <Input label="Apă țintă (ml)" type="number" value={form.water_target_ml} onChange={(e) => setForm({ ...form, water_target_ml: parseInt(e.target.value) || 0 })} />
        </div>
      </div>
      <div className="space-y-1.5">
        <label className="text-sm text-text-secondary">Note personale</label>
        <textarea className="w-full h-24 px-4 py-3 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30 resize-none"
          value={form.personal_notes} onChange={(e) => setForm({ ...form, personal_notes: e.target.value })} />
      </div>
      <Button onClick={handleSave} disabled={saving}>{saving ? <Spinner className="w-4 h-4" /> : null}{saving ? "Se salvează..." : "Salvează"}</Button>
    </div>
  )
}

function LLMTab({ profile, onUpdate }: { profile: Profile; onUpdate: (data: Partial<Profile>) => Promise<void> }) {
  const [provider, setProvider] = useState(profile.llm_provider || "ollama")
  const [host, setHost] = useState(profile.llm_host || "http://localhost:11434")
  const [model, setModel] = useState(profile.llm_model || "llama3.2:3b")
  const [apiKey, setApiKey] = useState(profile.gemini_api_key || "")
  const [showKey, setShowKey] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string; hint?: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)

  const [sysSpecs, setSysSpecs] = useState<{ total_ram_gb: number; total_vram_gb: number; cpu_cores: number } | null>(() => {
    try { return JSON.parse(localStorage.getItem("llm_sys_specs") || "null") } catch { return null }
  })
  const [ollamaStatus, setOllamaStatus] = useState<{ running: boolean; version: string; autostart: boolean; autostart_available: boolean; ollama_installed: boolean } | null>(null)
  const [models, setModels] = useState<any[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [showInsufficient, setShowInsufficient] = useState(false)
  const [pullTasks, setPullTasks] = useState<Record<string, { status: string; output: string }>>({})
  const [editingSpecs, setEditingSpecs] = useState(false)
  const [editRam, setEditRam] = useState(sysSpecs?.total_ram_gb || 0)
  const [editVram, setEditVram] = useState(sysSpecs?.total_vram_gb || 0)
  const [editCpu, setEditCpu] = useState(sysSpecs?.cpu_cores || 0)
  const [startingServer, setStartingServer] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const intervalsRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  useEffect(() => {
    return () => {
      intervalsRef.current.forEach(clearInterval)
      intervalsRef.current.clear()
    }
  }, [])

  useEffect(() => {
    api.get("/api/llm/status").then(({ data }) => setOllamaStatus(data)).catch(() => setError("Nu s-a putut verifica starea Ollama."))
  }, [])

  useEffect(() => {
    if (sysSpecs && provider === "ollama") {
      setModelsLoading(true); setError(null)
      api.get(`/api/llm/models?ram_gb=${sysSpecs.total_ram_gb}&vram_gb=${sysSpecs.total_vram_gb}`)
        .then(({ data }) => { setModels(data.models || []); setError(null) })
        .catch((e) => { setModels([]); setError("Nu s-au putut încărca modelele. Verifică dacă Ollama rulează și host-ul e corect.") })
        .finally(() => setModelsLoading(false))
    } else {
      setModels([])
    }
  }, [sysSpecs, provider])

  const handleDetect = async () => {
    setDetecting(true); setError(null)
    try {
      const { data } = await api.get("/api/llm/system-specs")
      setSysSpecs(data)
      setEditRam(data.total_ram_gb)
      setEditVram(data.total_vram_gb)
      setEditCpu(data.cpu_cores)
      localStorage.setItem("llm_sys_specs", JSON.stringify(data))
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Eroare la detectarea sistemului")
    } finally { setDetecting(false) }
  }

  const handleSaveSpecs = () => {
    const specs = { total_ram_gb: editRam, total_vram_gb: editVram, cpu_cores: editCpu }
    setSysSpecs(specs)
    localStorage.setItem("llm_sys_specs", JSON.stringify(specs))
    setEditingSpecs(false)
  }

  const handleTest = async () => {
    setTesting(true); setTestResult(null)
    try {
      const ep = provider === "ollama" ? "/api/integrations/test/ollama" : "/api/integrations/test/gemini"
      const body = provider === "ollama" ? { host, model } : { api_key: apiKey }
      const { data } = await api.post(ep, body)
      setTestResult(data)
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || "Connection failed"
      const hint = e?.response?.status === 401 ? "Token expirat. Loghează-te din nou." : e?.code === "ERR_NETWORK" ? "Verifică dacă serverul API rulează." : "Încearcă din nou."
      setTestResult({ ok: false, message: detail, hint })
    }
    finally { setTesting(false) }
  }

  const handleSave = async () => {
    setSaving(true)
    try { await onUpdate({ llm_provider: provider, llm_host: host, llm_model: model, gemini_api_key: apiKey }) }
    finally { setSaving(false) }
  }

  const handleSelectModel = async (name: string) => {
    setModel(name)
    await onUpdate({ llm_provider: provider, llm_host: host, llm_model: name, gemini_api_key: apiKey })
    setError(null)
    if (sysSpecs) {
      api.get(`/api/llm/models?ram_gb=${sysSpecs.total_ram_gb}&vram_gb=${sysSpecs.total_vram_gb}`)
        .then(({ data }) => setModels(data.models || []))
        .catch(() => {})
    }
  }

  const handlePull = async (modelName: string) => {
    try {
      const { data } = await api.post("/api/llm/pull", { model: modelName, host })
      const taskId = data.task_id
      setPullTasks(prev => ({ ...prev, [modelName]: { status: "starting", output: "" } }))

      const interval = setInterval(async () => {
        try {
          const { data: status } = await api.get(`/api/llm/pull/${taskId}`)
          setPullTasks(prev => ({ ...prev, [modelName]: { status: status.status, output: status.output || "" } }))
          if (status.status === "completed" || status.status === "failed") {
            clearInterval(interval)
            intervalsRef.current.delete(modelName)
            if (sysSpecs) {
              const { data: refreshed } = await api.get(`/api/llm/models?ram_gb=${sysSpecs.total_ram_gb}&vram_gb=${sysSpecs.total_vram_gb}`)
              setModels(refreshed.models || [])
            }
          }
        } catch {
          clearInterval(interval)
          intervalsRef.current.delete(modelName)
        }
      }, 2000)
      intervalsRef.current.set(modelName, interval)
    } catch {}
  }

  const handleStartServer = async () => {
    setStartingServer(true)
    try {
      await api.post("/api/llm/serve/start")
      setTimeout(async () => {
        const { data } = await api.get("/api/llm/status")
        setOllamaStatus(data)
        setStartingServer(false)
      }, 3000)
    } catch { setStartingServer(false) }
  }

  const handleStopServer = async () => {
    try {
      await api.post("/api/llm/serve/stop")
      await new Promise(r => setTimeout(r, 1000))
      const { data } = await api.get("/api/llm/status")
      setOllamaStatus(data)
    } catch {}
  }

  const handleToggleAutostart = async () => {
    const enabled = !ollamaStatus?.autostart
    try {
      await api.post("/api/llm/serve/autostart", { enabled })
      setOllamaStatus(prev => prev ? { ...prev, autostart: enabled } : prev)
    } catch {}
  }

  const tierColor: Record<string, string> = {
    recommended: "bg-emerald-500/10 text-emerald-400",
    ok: "bg-blue-500/10 text-blue-400",
    minimum: "bg-yellow-500/10 text-yellow-400",
    insufficient: "bg-red-500/10 text-red-400",
  }

  const tierLabel: Record<string, string> = {
    recommended: "Recomandat",
    ok: "OK",
    minimum: "Minim",
    insufficient: "Insuficient",
  }

  const groupedModels = models.reduce<Record<string, any[]>>((acc, m) => {
    const t = m.tier || "insufficient"
    if (!acc[t]) acc[t] = []
    acc[t].push(m)
    return acc
  }, {})

  const renderModelRow = (m: any) => {
    const pullTask = pullTasks[m.name]
    const isPulling = pullTask && (pullTask.status === "starting" || pullTask.status === "running")
    const isFailed = pullTask?.status === "failed"
    const isCurrent = m.current || m.name === model

    return (
      <tr key={m.name}
        onClick={() => { if (!isPulling && !isFailed) handleSelectModel(m.name) }}
        className={`border-b border-border/50 transition-colors ${isCurrent ? "bg-emerald-500/5" : "hover:bg-surface/50"} ${isPulling || isFailed ? "" : "cursor-pointer"}`}>
        <td className="py-2.5 pr-2 w-5 align-top">{isCurrent && <span className="text-emerald-400 text-sm">✓</span>}</td>
        <td className="py-2.5 px-2">
          <div className="text-text-primary font-medium text-sm">{m.name}</div>
          {m.description && <div className="text-xs text-text-muted">{m.description}</div>}
          {isPulling && (
            <details className="mt-1">
              <summary className="text-xs text-text-muted cursor-pointer">Progres descărcare</summary>
              <pre className="mt-1 max-h-20 overflow-y-auto p-2 rounded bg-surface/50 text-[10px] leading-tight text-text-muted">{pullTask?.output || ""}</pre>
            </details>
          )}
          {isFailed && <div className="text-xs text-red-400 mt-1">Eroare la descărcare</div>}
        </td>
        <td className="py-2.5 px-2 text-right text-text-secondary whitespace-nowrap text-xs align-top">{m.size_gb.toFixed(1)} GB</td>
        <td className="py-2.5 px-2 text-right text-text-secondary whitespace-nowrap text-xs align-top">{m.ram_min_gb} GB</td>
        <td className="py-2.5 px-2 text-right text-text-secondary whitespace-nowrap text-xs align-top">{m.vram_min_gb > 0 ? `${m.vram_min_gb} GB` : "CPU"}</td>
        <td className="py-2.5 px-2 text-center align-top">
          <div className="flex flex-col items-center gap-0.5">
            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${tierColor[m.tier] || tierColor.insufficient}`}>
              {tierLabel[m.tier] || "?"}
            </span>
            {m.gpu_ready && <span className="text-[10px] font-medium text-purple-400">GPU</span>}
          </div>
        </td>
        <td className="py-2.5 px-2 text-text-secondary text-xs hidden md:table-cell align-top">{m.use_case}</td>
        <td className="py-2.5 pl-2 text-right align-top">
          {isPulling ? (
            <div className="flex items-center gap-1 justify-end">
              <Spinner className="w-3 h-3" />
              <span className="text-xs text-text-muted">Descărcare...</span>
            </div>
          ) : m.installed ? (
            <span className="text-xs text-emerald-400 font-medium">Instalat</span>
          ) : m.from_ollama_only ? (
            <span className="text-xs text-text-muted">—</span>
          ) : (
            <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); handlePull(m.name) }}>
              Instalează
            </Button>
          )}
        </td>
      </tr>
    )
  }

  return (
    <div className="space-y-5">
      <div className="p-4 rounded-xl bg-surface border border-border space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Specificații sistem</h3>
          <div className="flex gap-2">
            {sysSpecs && (
              <button onClick={() => { setEditingSpecs(!editingSpecs); setEditRam(sysSpecs.total_ram_gb); setEditVram(sysSpecs.total_vram_gb); setEditCpu(sysSpecs.cpu_cores) }}
                className="text-xs text-text-secondary hover:text-text-primary px-2 py-1 rounded-lg border border-border">
                {editingSpecs ? "Anulează" : "Editează"}
              </button>
            )}
            <Button variant="secondary" size="sm" onClick={handleDetect} disabled={detecting}>
              {detecting ? <Spinner className="w-3 h-3" /> : null}
              {detecting ? "Se detectează..." : "Detectează sistemul"}
            </Button>
          </div>
        </div>
        {sysSpecs && !editingSpecs && (
          <div className="grid grid-cols-3 gap-3">
            <div className="p-2.5 rounded-lg bg-surface/50 border border-border text-center">
              <div className="text-xs text-text-muted">RAM</div>
              <div className="text-sm font-semibold text-text-primary">{sysSpecs.total_ram_gb} GB</div>
            </div>
            <div className="p-2.5 rounded-lg bg-surface/50 border border-border text-center">
              <div className="text-xs text-text-muted">VRAM</div>
              <div className="text-sm font-semibold text-text-primary">{sysSpecs.total_vram_gb > 0 ? `${sysSpecs.total_vram_gb} GB` : "—"}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-surface/50 border border-border text-center">
              <div className="text-xs text-text-muted">CPU</div>
              <div className="text-sm font-semibold text-text-primary">{sysSpecs.cpu_cores} nuclee</div>
            </div>
          </div>
        )}
        {sysSpecs && editingSpecs && (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-text-muted">RAM (GB)</label>
                <input type="number" className="w-full h-9 px-3 rounded-lg bg-surface border border-border text-text-primary text-sm focus:outline-none focus:border-primary/30"
                  value={editRam} onChange={e => setEditRam(parseFloat(e.target.value) || 0)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-text-muted">VRAM (GB)</label>
                <input type="number" className="w-full h-9 px-3 rounded-lg bg-surface border border-border text-text-primary text-sm focus:outline-none focus:border-primary/30"
                  value={editVram} onChange={e => setEditVram(parseFloat(e.target.value) || 0)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-text-muted">CPU nuclee</label>
                <input type="number" className="w-full h-9 px-3 rounded-lg bg-surface border border-border text-text-primary text-sm focus:outline-none focus:border-primary/30"
                  value={editCpu} onChange={e => setEditCpu(parseInt(e.target.value) || 0)} />
              </div>
            </div>
            <Button size="sm" onClick={handleSaveSpecs}>Salvează specificațiile</Button>
          </div>
        )}
        {!sysSpecs && <p className="text-xs text-text-muted">Apasă "Detectează sistemul" pentru a vedea recomandări de modele.</p>}
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-sm text-red-400">
          {error}
        </div>
      )}

      {provider === "ollama" && (
        <div className="p-3 rounded-xl bg-surface border border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${ollamaStatus?.running ? "bg-emerald-400" : "bg-red-400"}`} />
            <span className="text-sm text-text-primary">
              {ollamaStatus?.running ? "Ollama rulează" : "Ollama oprit"}
            </span>
            {ollamaStatus?.version && <span className="text-xs text-text-muted">{ollamaStatus.version}</span>}
          </div>
          <div className="flex items-center gap-2">
            {ollamaStatus?.autostart_available && (
              <button onClick={handleToggleAutostart}
                className={`text-xs px-2 py-1 rounded-lg border transition-colors ${ollamaStatus?.autostart ? "bg-emerald-500/10 border-emerald-500 text-emerald-400" : "bg-surface border-border text-text-secondary"}`}>
                {ollamaStatus?.autostart ? "Auto ON" : "Auto OFF"}
              </button>
            )}
            {ollamaStatus?.running ? (
              <Button variant="secondary" size="sm" onClick={handleStopServer}>Stop</Button>
            ) : (
              <Button size="sm" onClick={handleStartServer} disabled={startingServer}>
                {startingServer ? <Spinner className="w-3 h-3" /> : null}Start
              </Button>
            )}
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        <label className="text-sm text-text-secondary">Provider</label>
        <div className="flex gap-3">
          <button onClick={() => setProvider("ollama")}
            className={`flex-1 h-11 rounded-xl border text-sm font-medium transition-all ${provider === "ollama" ? "bg-emerald-500/10 border-emerald-500 text-emerald-400" : "bg-surface border-border text-text-secondary hover:text-text-primary"}`}>
            Local (Ollama)
          </button>
          <button onClick={() => setProvider("gemini")}
            className={`flex-1 h-11 rounded-xl border text-sm font-medium transition-all ${provider === "gemini" ? "bg-emerald-500/10 border-emerald-500 text-emerald-400" : "bg-surface border-border text-text-secondary hover:text-text-primary"}`}>
            Cloud (Gemini)
          </button>
        </div>
      </div>

      {provider === "ollama" && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Host" value={host} onChange={(e) => setHost(e.target.value)} placeholder="http://localhost:11434" />
            <Input label="Model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="llama3.2:3b" />
          </div>

          {sysSpecs && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Modele disponibile</h3>
                <button onClick={() => {
                  if (sysSpecs) {
                    setModelsLoading(true)
                    api.get(`/api/llm/models?ram_gb=${sysSpecs.total_ram_gb}&vram_gb=${sysSpecs.total_vram_gb}`)
                      .then(({ data }) => setModels(data.models || []))
                      .catch(() => {})
                      .finally(() => setModelsLoading(false))
                  }
                }} className="text-xs text-text-secondary hover:text-text-primary flex items-center gap-1">
                  {modelsLoading && <Spinner className="w-3 h-3" />}
                  {modelsLoading ? "Se reîmprospătează..." : "Reîmprospătează"}
                </button>
              </div>

              {modelsLoading && models.length === 0 ? (
                <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>
              ) : models.length === 0 ? (
                <p className="text-sm text-text-muted text-center py-4">Niciun model găsit în Ollama.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-2 text-text-muted font-medium w-5"></th>
                        <th className="text-left py-2 px-2 text-text-muted font-medium">Model</th>
                        <th className="text-right py-2 px-2 text-text-muted font-medium whitespace-nowrap">Dimensiune</th>
                        <th className="text-right py-2 px-2 text-text-muted font-medium whitespace-nowrap">RAM</th>
                        <th className="text-right py-2 px-2 text-text-muted font-medium whitespace-nowrap">VRAM</th>
                        <th className="text-center py-2 px-2 text-text-muted font-medium">Compatibilitate</th>
                        <th className="text-left py-2 px-2 text-text-muted font-medium hidden md:table-cell">Caz</th>
                        <th className="text-right py-2 pl-2 text-text-muted font-medium">Acțiune</th>
                      </tr>
                    </thead>
                    <tbody>
                      {["recommended", "ok", "minimum"].flatMap(tier =>
                        (groupedModels[tier] || []).map(m => renderModelRow(m))
                      )}
                      {(groupedModels["insufficient"] || []).length > 0 && (
                        <>
                          <tr>
                            <td colSpan={8} className="pt-3">
                              <button onClick={() => setShowInsufficient(!showInsufficient)}
                                className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary">
                                {showInsufficient ? "▼" : "▶"} {groupedModels["insufficient"].length} modele insuficiente
                              </button>
                            </td>
                          </tr>
                          {showInsufficient && groupedModels["insufficient"].map(m => renderModelRow(m))}
                        </>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {provider === "gemini" && (
        <div className="space-y-1.5">
          <label className="text-sm text-text-secondary">Gemini API Key</label>
          <div className="flex gap-2">
            <input type={showKey ? "text" : "password"}
              className="flex-1 h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
              value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="AIza..." />
            <button onClick={() => setShowKey(!showKey)}
              className="px-3 h-11 rounded-xl bg-surface border border-border text-text-secondary hover:text-text-primary text-xs">
              {showKey ? "Ascunde" : "Arată"}
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <Button variant="secondary" onClick={handleTest} disabled={testing}>
          {testing ? <Spinner className="w-4 h-4" /> : null}{testing ? "Se testează..." : "Test connection"}
        </Button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Spinner className="w-4 h-4" /> : null}{saving ? "Se salvează..." : "Salvează"}
        </Button>
      </div>

      {testResult && (
        <div className={`p-3 rounded-xl text-sm ${testResult.ok ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
          <p>{testResult.message}</p>
          {testResult.hint && <p className="text-xs text-text-muted mt-2">{testResult.hint}</p>}
        </div>
      )}
    </div>
  )
}

function IntegrationsTab() {
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string; hint?: string } | null>>({})
  const [testing, setTesting] = useState<string | null>(null)
  const integrations = [
    { key: "weather", label: "OpenWeather", endpoint: "/api/integrations/test/weather" },
  ]

  const handleTest = async (key: string, endpoint: string) => {
    setTesting(key)
    setTestResults((p) => ({ ...p, [key]: null }))
    try {
      const { data } = await api.post(endpoint)
      setTestResults((p) => ({ ...p, [key]: data }))
    } catch { setTestResults((p) => ({ ...p, [key]: { ok: false, message: "Eroare conexiune", hint: "Verifică dacă serverul API rulează." } })) }
    finally { setTesting(null) }
  }

  return (
    <div className="space-y-4">
      {integrations.map((int) => (
        <div key={int.key} className="p-4 rounded-xl bg-surface border border-border">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">{int.label}</div>
              <div className="text-xs text-text-muted mt-0.5">
                {testResults[int.key]?.ok ? "Activat" : testResults[int.key] && !testResults[int.key]?.ok ? testResults[int.key].message : "Netestat"}
              </div>
            </div>
            <Button variant="secondary" size="sm" onClick={() => handleTest(int.key, int.endpoint)} disabled={testing === int.key}>
              {testing === int.key ? <Spinner className="w-3 h-3" /> : null}Test
            </Button>
          </div>
          {testResults[int.key] && !testResults[int.key]?.ok && testResults[int.key]?.hint && (
            <p className="text-xs text-yellow-400 mt-3">{testResults[int.key]?.hint}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function LoreTab() {
  const qc = useQueryClient()
  const { data: facts, isLoading } = useQuery<MemoryFact[]>({
    queryKey: ["memory"],
    queryFn: async () => { const { data } = await api.get("/api/memory?limit=200"); return data },
  })
  const addMut = useMutation({
    mutationFn: async (body: { fact: string; category: string }) => { await api.post("/api/memory", body) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memory"] }),
  })
  const delMut = useMutation({
    mutationFn: async (id: number) => { await api.delete(`/api/memory/${id}`) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memory"] }),
  })
  const [newFact, setNewFact] = useState("")
  const [newCat, setNewCat] = useState("general")

  const grouped = facts?.reduce<Record<string, MemoryFact[]>>((acc, f) => {
    const key = f.category || "general"; (acc[key] ??= []).push(f); return acc
  }, {})

  if (isLoading) return <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>

  return (
    <div className="space-y-5">
      <div className="flex gap-2">
        <input className="flex-1 h-11 px-4 rounded-xl bg-surface border border-border text-text-primary focus:outline-none focus:border-primary/30"
          placeholder="Fapt nou..." value={newFact} onChange={(e) => setNewFact(e.target.value)} />
        <select className="h-11 px-3 rounded-xl bg-surface border border-border text-text-primary"
          value={newCat} onChange={(e) => setNewCat(e.target.value)}>
          <option value="general">General</option>
          <option value="personal">Personal</option>
          <option value="preference">Preference</option>
          <option value="pattern">Pattern</option>
          <option value="achievement">Achievement</option>
        </select>
        <Button size="sm" onClick={() => { if (newFact.trim()) { addMut.mutate({ fact: newFact, category: newCat }); setNewFact("") } }}>
          Adaugă
        </Button>
      </div>
      {grouped && Object.entries(grouped).map(([cat, items]) => (
        <div key={cat}>
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-2">{cat}</h3>
          <div className="space-y-2">
            {items.map((f) => (
              <div key={f.id} className="flex items-start gap-2 p-3 rounded-xl bg-surface border border-border">
                <p className="flex-1 text-sm">{f.fact}</p>
                <button onClick={() => delMut.mutate(f.id)} className="text-red-400 hover:text-red-300 p-1 shrink-0">✕</button>
              </div>
            ))}
          </div>
        </div>
      ))}
      {facts?.length === 0 && <p className="text-sm text-text-muted text-center py-8">Nicio amintire încă.</p>}
    </div>
  )
}

const safeArr = (arr: any) => Array.isArray(arr) ? arr : []

function CorrelationsTab() {
  const { data: correlations, isLoading, refetch } = useQuery({
    queryKey: ["correlations"],
    queryFn: async () => { const { data } = await api.get("/api/correlations"); return data as any[] },
    enabled: false,
  })
  const { data: history } = useQuery<Record<string, any>[]>({
    queryKey: ["correlations-history"],
    queryFn: async () => { const { data } = await api.get("/api/correlations/history"); return Array.isArray(data) ? data : [] },
  })

  const cors = safeArr(correlations)
  const hist = safeArr(history)

  return (
    <div className="space-y-5">
      <Button onClick={() => refetch()} disabled={isLoading} size="sm">
        {isLoading ? <Spinner className="w-4 h-4" /> : null}Analizează acum
      </Button>
      {cors.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Corelații active</h3>
          {cors.map((c: any, i: number) => (
            <div key={i} className="p-4 rounded-xl bg-surface border border-border space-y-2">
              <p className="text-sm font-medium">{c.correlation}</p>
              <div className="flex gap-2 text-xs">
                <span className={`px-2 py-0.5 rounded-full ${c.strength === "puternică" ? "bg-emerald-500/10 text-emerald-400" : "bg-yellow-500/10 text-yellow-400"}`}>
                  {c.strength}
                </span>
              </div>
              {c.recommendation && <p className="text-xs text-text-secondary">{c.recommendation}</p>}
              {c.data_evidence && <p className="text-xs text-text-muted">{c.data_evidence}</p>}
            </div>
          ))}
        </div>
      ) : correlations ? (
        <p className="text-sm text-text-muted">Nu sunt suficiente date pentru corelații (minim 7 zile).</p>
      ) : null}
      {hist.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Istoric corelații salvate</h3>
          {hist.map((h: any) => (
            <div key={h.id} className="p-3 rounded-xl bg-surface border border-border text-sm">
              <p>{h.fact}</p>
              <p className="text-xs text-text-muted mt-1">{new Date(h.created_at).toLocaleDateString()}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TimelineTab() {
  const [days, setDays] = useState(7)
  const [mod, setMod] = useState("")
  const { data: _entries, isLoading } = useQuery({
    queryKey: ["timeline", days, mod],
    queryFn: async () => {
      const p = new URLSearchParams({ days: String(days) })
      if (mod) p.set("module", mod)
      const { data } = await api.get(`/api/timeline?${p}`)
      return data as any[]
    },
  })
  const entries = safeArr(_entries)

  return (
    <div className="space-y-5">
      <div className="flex gap-3">
        <div className="space-y-1.5">
          <label className="text-xs text-text-secondary">Zile</label>
          <select className="h-10 px-3 rounded-xl bg-surface border border-border text-text-primary text-sm"
            value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={1}>Azi</option>
            <option value={7}>7 zile</option>
            <option value={30}>30 zile</option>
            <option value={90}>90 zile</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-text-secondary">Modul</label>
          <select className="h-10 px-3 rounded-xl bg-surface border border-border text-text-primary text-sm"
            value={mod} onChange={(e) => setMod(e.target.value)}>
            <option value="">Toate</option>
            <option value="tasks">Tasks</option>
            <option value="finance">Finance</option>
            <option value="health">Health</option>
            <option value="workout">Workout</option>
            <option value="mood">Mood</option>
            <option value="goals">Goals</option>
            <option value="reading">Reading</option>
          </select>
        </div>
      </div>
      {isLoading ? (
        <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>
      ) : entries.length > 0 ? (
        <div className="space-y-2">
          {entries.map((e: any, i: number) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-surface border border-border text-sm">
              <span className="text-xs text-text-muted shrink-0 w-16">
                {new Date(e.created_at).toLocaleString("ro-RO", { hour: "2-digit", minute: "2-digit" })}
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase ${e.success ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                {e.module || "?"}
              </span>
              <span className="flex-1 text-text-secondary truncate">{e.intent}</span>
              {e.error_message && <span className="text-xs text-red-400 truncate max-w-[200px]" title={e.error_message}>!</span>}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-text-muted text-center py-8">Nicio activitate în această perioadă.</p>
      )}
    </div>
  )
}

function AutoLearningTab() {
  const { data: behavior, isLoading } = useQuery({
    queryKey: ["behavior"],
    queryFn: async () => {
      const { data } = await api.get("/api/profile/behavior")
      return data as { frequent_categories: Record<string, Record<string, number>> }
    },
  })

  if (isLoading) return <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>

  const cats = behavior?.frequent_categories || {}

  return (
    <div className="space-y-5">
      <p className="text-sm text-text-secondary">
        Lora învață automat din comportamentul tău. Iată ce a descoperit în ultimele 30 de zile:
      </p>
      {Object.keys(cats).length === 0 ? (
        <p className="text-sm text-text-muted">Încă nu sunt suficiente date. Continuă să folosești Lora.</p>
      ) : (
        Object.entries(cats).map(([domain, items]) => (
          <div key={domain}>
            <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-2">{domain}</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(items as Record<string, number>).map(([name, count]) => (
                <span key={name} className="px-3 py-1.5 rounded-lg bg-surface border border-border text-xs font-medium">
                  {name} <span className="text-text-muted">({count}x)</span>
                </span>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}

// ---- Phase 3: Jobs Tab ----

function JobsTab() {
  const qc = useQueryClient()
  const { data: _jobs, isLoading } = useQuery<JobConfig[]>({
    queryKey: ["jobs"],
    queryFn: async () => { const { data } = await api.get("/api/jobs"); return data },
  })
  const jobs = safeArr(_jobs)
  const updMut = useMutation({
    mutationFn: async ({ name, body }: { name: string; body: Partial<JobConfig> }) => {
      await api.put(`/api/jobs/${name}`, body)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })
  const syncMut = useMutation({
    mutationFn: async () => { await api.post("/api/jobs/sync") },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })

  if (isLoading) return <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-secondary">{jobs.length} joburi configurate</p>
        <Button size="sm" variant="secondary" onClick={() => syncMut.mutate()} disabled={syncMut.isPending}>
          {syncMut.isPending ? <Spinner className="w-3 h-3" /> : null}Sincronizează
        </Button>
      </div>
      {jobs.length === 0 ? (
        <p className="text-sm text-text-muted text-center py-8">Niciun job configurat. Apasă "Sincronizează" pentru a importa joburile implicite.</p>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div key={job.job_name} className="flex items-center gap-3 p-3 rounded-xl bg-surface border border-border">
              <button onClick={() => updMut.mutate({ name: job.job_name, body: { enabled: !job.enabled } })}
                className={`w-8 h-5 rounded-full transition-colors ${job.enabled ? "bg-emerald-500" : "bg-border"}`}>
                <div className={`w-3.5 h-3.5 rounded-full bg-white transition-transform ${job.enabled ? "translate-x-4" : "translate-x-0.5"}`} />
              </button>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{job.job_name}</div>
                <div className="text-xs text-text-muted">
                  {job.cron_time || "fără program"} {job.last_run && `• ultima dată ${new Date(job.last_run).toLocaleDateString()}`}
                </div>
              </div>
              {job.last_error && <span className="text-xs text-red-400 truncate max-w-[150px]" title={job.last_error}>Eroare</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---- Phase 3: Logs Tab ----

function LogsTab() {
  const [days, setDays] = useState(7)
  const [mod, setMod] = useState("")
  const [success, setSuccess] = useState<string>("")
  const [page, setPage] = useState(0)

  const { data: stats } = useQuery<LogStats>({
    queryKey: ["log-stats", days],
    queryFn: async () => { const { data } = await api.get(`/api/logs/stats?days=${days}`); return data },
  })

  const { data: _logs, isLoading } = useQuery<LogResponse>({
    queryKey: ["logs", days, mod, success, page],
    queryFn: async () => {
      const p = new URLSearchParams({ days: String(days), limit: "50", offset: String(page * 50) })
      if (mod) p.set("module", mod)
      if (success) p.set("success", success)
      const { data } = await api.get(`/api/logs?${p}`)
      return data
    },
  })
  const logs = _logs as LogResponse | undefined
  const logEntries = safeArr(logs?.entries)
  const byModule = safeArr(stats?.by_module)

  return (
    <div className="space-y-5">
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-4 rounded-xl bg-surface border border-border">
            <div className="text-xs text-text-muted">Total</div>
            <div className="text-xl font-semibold mt-1">{stats.total}</div>
          </div>
          <div className="p-4 rounded-xl bg-surface border border-border">
            <div className="text-xs text-text-muted">Erori</div>
            <div className="text-xl font-semibold mt-1 text-red-400">{stats.errors}</div>
          </div>
          <div className="p-4 rounded-xl bg-surface border border-border">
            <div className="text-xs text-text-muted">Success Rate</div>
            <div className="text-xl font-semibold mt-1 text-emerald-400">{stats.success_rate}%</div>
          </div>
          <div className="p-4 rounded-xl bg-surface border border-border">
            <div className="text-xs text-text-muted">Module active</div>
            <div className="text-xl font-semibold mt-1">{byModule.length}</div>
          </div>
        </div>
      )}
      <div className="flex gap-3 flex-wrap">
        <div className="space-y-1.5">
          <label className="text-xs text-text-secondary">Zile</label>
          <select className="h-10 px-3 rounded-xl bg-surface border border-border text-text-primary text-sm"
            value={days} onChange={(e) => { setDays(Number(e.target.value)); setPage(0) }}>
            <option value={1}>Azi</option>
            <option value={7}>7 zile</option>
            <option value={30}>30 zile</option>
            <option value={90}>90 zile</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-text-secondary">Modul</label>
          <select className="h-10 px-3 rounded-xl bg-surface border border-border text-text-primary text-sm"
            value={mod} onChange={(e) => { setMod(e.target.value); setPage(0) }}>
            <option value="">Toate</option>
            {byModule.map((m: any) => (
              <option key={m.module} value={m.module}>{m.module}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-text-secondary">Status</label>
          <select className="h-10 px-3 rounded-xl bg-surface border border-border text-text-primary text-sm"
            value={success} onChange={(e) => { setSuccess(e.target.value); setPage(0) }}>
            <option value="">Toate</option>
            <option value="true">Success</option>
            <option value="false">Erori</option>
          </select>
        </div>
      </div>
      {isLoading ? (
        <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>
      ) : logEntries.length > 0 ? (
        <>
          <div className="space-y-2">
            {logEntries.map((e: any) => (
              <div key={e.id} className="flex items-center gap-3 p-3 rounded-xl bg-surface border border-border text-sm">
                <span className="text-xs text-text-muted shrink-0 w-16">
                  {new Date(e.created_at).toLocaleString("ro-RO", { hour: "2-digit", minute: "2-digit" })}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase ${e.success ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                  {e.module || "?"}
                </span>
                <span className="flex-1 text-text-secondary truncate">{e.intent}</span>
                {e.error_message && <span className="text-xs text-red-400 truncate max-w-[200px]" title={e.error_message}>!</span>}
              </div>
            ))}
          </div>
          {logs.total > 50 && (
            <div className="flex items-center justify-center gap-3 text-sm">
              <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
                ← Anterioară
              </Button>
              <span className="text-text-muted">Pagina {page + 1} / {Math.ceil(logs.total / 50)}</span>
              <Button variant="secondary" size="sm" disabled={(page + 1) * 50 >= logs.total} onClick={() => setPage(page + 1)}>
                Următoarea →
              </Button>
            </div>
          )}
        </>
      ) : (
        <p className="text-sm text-text-muted text-center py-8">Nicio activitate în această perioadă.</p>
      )}
    </div>
  )
}

// ---- Phase 3: Calendar Sync Tab ----

function CalendarSyncTab() {
  const { data: _status, isLoading, refetch } = useQuery<CalendarSyncStatus>({
    queryKey: ["calendar-sync-status"],
    queryFn: async () => { const { data } = await api.get("/api/calendar-sync/status"); return data },
  })
  const status = _status as CalendarSyncStatus | undefined
  const triggerMut = useMutation({
    mutationFn: async () => { const { data } = await api.post("/api/calendar-sync/trigger"); return data },
    onSuccess: () => refetch(),
  })

  if (isLoading) return <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>

  const byType = safeArr(status?.by_type)
  const errors = safeArr(status?.recent_errors)

  return (
    <div className="space-y-5">
      {status && (
        <div className="grid grid-cols-2 gap-3">
          <div className="p-4 rounded-xl bg-surface border border-border">
            <div className="text-xs text-text-muted">Total sincronizări</div>
            <div className="text-xl font-semibold mt-1">{status.total_synced}</div>
          </div>
          <div className="p-4 rounded-xl bg-surface border border-border">
            <div className="text-xs text-text-muted">Tipuri de date</div>
            <div className="flex gap-1 mt-1 flex-wrap">
              {byType.map((t: any) => (
                <span key={t.lora_type} className="px-2 py-0.5 rounded-lg bg-surface border border-border text-[10px]">
                  {t.lora_type} ({t.count})
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
      {status?.last_sync && (
        <div className="p-3 rounded-xl bg-surface border border-border text-sm">
          <span className="text-text-muted">Ultima sincronizare: </span>
          {new Date(status.last_sync.synced_at).toLocaleString()} — {status.last_sync.summary}
        </div>
      )}
      {errors.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Erori recente</h3>
          {errors.slice(0, 5).map((e: any, i: number) => (
            <div key={i} className="p-3 rounded-xl bg-surface border border-border text-sm text-red-400">
              {e.error_message || "Eroare necunoscută"}
            </div>
          ))}
        </div>
      )}
      <Button onClick={() => triggerMut.mutate()} disabled={triggerMut.isPending}>
        {triggerMut.isPending ? <Spinner className="w-4 h-4" /> : null}Sincronizează acum
      </Button>
    </div>
  )
}

// ---- Phase 3: Export Tab ----

const EXPORT_MODULES = [
  { key: "tasks", label: "Tasks" },
  { key: "finance", label: "Finance" },
  { key: "health", label: "Health" },
  { key: "workout", label: "Workout" },
  { key: "mood", label: "Mood" },
  { key: "notes", label: "Notes" },
  { key: "goals", label: "Goals" },
  { key: "reading", label: "Reading" },
  { key: "events", label: "Events" },
  { key: "shopping", label: "Shopping" },
  { key: "university", label: "University" },
]

function ExportTab() {
  const [selected, setSelected] = useState("tasks")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [exporting, setExporting] = useState(false)

  const handleExport = async () => {
    setExporting(true)
    try {
      const p = new URLSearchParams()
      if (startDate) p.set("start_date", startDate)
      if (endDate) p.set("end_date", endDate)
      const qs = p.toString()
      const url = `/api/export/${selected}${qs ? `?${qs}` : ""}`
      const { data } = await api.get(url)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
      const a = document.createElement("a")
      a.href = URL.createObjectURL(blob)
      a.download = `${selected}_${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(a.href)
    } finally { setExporting(false) }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-text-secondary">Exportă datele dintr-un modul în format JSON.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <label className="text-sm text-text-secondary">Modul</label>
          <select className="w-full h-11 px-4 rounded-xl bg-surface border border-border text-text-primary"
            value={selected} onChange={(e) => setSelected(e.target.value)}>
            {EXPORT_MODULES.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </div>
        <div />
        <Input label="De la (opțional)" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        <Input label="Până la (opțional)" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
      </div>
      <Button onClick={handleExport} disabled={exporting}>
        {exporting ? <Spinner className="w-4 h-4" /> : <Download className="w-4 h-4" />}
        {exporting ? "Se exportă..." : "Exportă JSON"}
      </Button>
    </div>
  )
}

// ---- Phase 3: Backups Tab ----

function BackupsTab() {
  const qc = useQueryClient()
  const { data: config, isLoading: cfgLoading } = useQuery<BackupConfig>({
    queryKey: ["backup-config"],
    queryFn: async () => { const { data } = await api.get("/api/backups/config"); return data },
  })
  const { data: _backups, isLoading: bkpLoading } = useQuery<BackupRecord[]>({
    queryKey: ["backups"],
    queryFn: async () => { const { data } = await api.get("/api/backups"); return data },
  })
  const backups = safeArr(_backups)
  const cfgMut = useMutation({
    mutationFn: async (body: Partial<BackupConfig>) => { await api.put("/api/backups/config", body) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backup-config"] }),
  })
  const triggerMut = useMutation({
    mutationFn: async () => { await api.post("/api/backups") },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backups", "backup-config"] }),
  })
  const [form, setForm] = useState<{ enabled: boolean; cron: string; retention: number } | null>(null)
  const [dirty, setDirty] = useState(false)

  if (config && !form) setForm({ enabled: config.enabled, cron: config.schedule_cron, retention: config.retention_days })

  const handleSaveConfig = () => {
    if (!form) return
    cfgMut.mutate({ enabled: form.enabled, schedule_cron: form.cron, retention_days: form.retention })
    setDirty(false)
  }

  if (cfgLoading) return <div className="py-8 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>
  if (!form) return null

  return (
    <div className="space-y-5">
      <div className="p-4 rounded-xl bg-surface border border-border space-y-4">
        <h3 className="text-sm font-medium">Configurație backup</h3>
        <div className="flex items-center gap-3">
          <button onClick={() => { setForm({ ...form, enabled: !form.enabled }); setDirty(true) }}
            className={`w-10 h-6 rounded-full transition-colors ${form.enabled ? "bg-emerald-500" : "bg-border"}`}>
            <div className={`w-4 h-4 rounded-full bg-white transition-transform ${form.enabled ? "translate-x-5" : "translate-x-0.5"}`} />
          </button>
          <span className="text-sm">{form.enabled ? "Activat" : "Dezactivat"}</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="Cron expression" value={form.cron} onChange={(e) => { setForm({ ...form, cron: e.target.value }); setDirty(true) }} placeholder="0 4 * * 0" />
          <Input label="Retention (zile)" type="number" value={form.retention} onChange={(e) => { setForm({ ...form, retention: parseInt(e.target.value) || 30 }); setDirty(true) }} />
        </div>
        {dirty && <Button size="sm" onClick={handleSaveConfig} disabled={cfgMut.isPending}>Salvează config</Button>}
      </div>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Istoric backupuri</h3>
        <Button size="sm" onClick={() => triggerMut.mutate()} disabled={triggerMut.isPending}>
          {triggerMut.isPending ? <Spinner className="w-3 h-3" /> : null}Rulează backup
        </Button>
      </div>
      {bkpLoading ? (
        <div className="py-4 text-center"><Spinner className="w-5 h-5 mx-auto" /></div>
      ) : backups.length > 0 ? (
        <div className="space-y-2">
          {backups.map((b: any) => (
            <div key={b.id} className="flex items-center gap-3 p-3 rounded-xl bg-surface border border-border text-sm">
              <span className={`w-2 h-2 rounded-full ${b.status === "success" ? "bg-emerald-400" : b.status === "failed" ? "bg-red-400" : "bg-yellow-400"}`} />
              <span className="flex-1 text-text-secondary">
                {new Date(b.created_at).toLocaleString()} {b.file_name && `— ${b.file_name}`}
              </span>
              {b.file_size_bytes && <span className="text-xs text-text-muted">{(b.file_size_bytes / 1024).toFixed(0)} KB</span>}
              {b.error_message && <span className="text-xs text-red-400 truncate max-w-[200px]" title={b.error_message}>Eroare</span>}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-text-muted text-center py-4">Niciun backup încă.</p>
      )}
    </div>
  )
}

export default function Space() {
  const [active, setActive] = useState<TabKey>("profile")
  const qc = useQueryClient()

  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: async () => { const { data } = await api.get("/api/profile"); return data as Profile },
  })

  const upd = useMutation({
    mutationFn: async (body: Partial<Profile>) => { const { data } = await api.put("/api/profile", body); return data as Profile },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile"] }),
  })

  if (isLoading) return <div className="flex items-center justify-center min-h-[50vh]"><Spinner className="w-6 h-6" /></div>
  if (!profile) return <div className="p-6 text-center text-text-secondary">Nu s-a putut încărca profilul.</div>

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="card-liquid-page">
      <div className="card-liquid-page-content p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-text-primary">Lora Space</h1>
          <p className="text-sm text-text-secondary mt-1">Administrează-ți asistentul personal</p>
        </div>
        <div className="flex gap-1 mb-6 overflow-x-auto pb-1">
          {tabs.map((t) => {
            const Icon = t.icon
            return (
              <button key={t.key} onClick={() => setActive(t.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${active === t.key ? "bg-surface text-text-primary border border-border" : "text-text-secondary hover:text-text-primary border border-transparent"}`}>
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            )
          })}
        </div>
        {active === "profile" && <ProfileTab profile={profile} onUpdate={(d) => upd.mutateAsync(d)} />}
        {active === "llm" && <LLMTab profile={profile} onUpdate={(d) => upd.mutateAsync(d)} />}
        {active === "integrations" && <IntegrationsTab />}
        {active === "lore" && <LoreTab />}
        {active === "correlations" && <CorrelationsTab />}
        {active === "timeline" && <TimelineTab />}
        {active === "auto" && <AutoLearningTab />}
        {active === "jobs" && <JobsTab />}
        {active === "logs" && <LogsTab />}
        {active === "calendar-sync" && <CalendarSyncTab />}
        {active === "export" && <ExportTab />}
        {active === "backups" && <BackupsTab />}
      </div>
    </motion.div>
  )
}
