import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { api } from "../../api/client"

interface Service {
  name: string
  port: number
  icon: string
  up: boolean
}

interface DiskInfo {
  total_gb: number
  used_gb: number
  used_pct: number
}

interface SystemStats {
  cpu_usage: number
  ram_used_mb: number
  ram_total_mb: number
  ram_used_pct: number
  ssd: DiskInfo
  hdd: DiskInfo
}

const FALLBACK = {
  services: [] as Service[],
  system: { cpu_usage: 0, ram_used_mb: 0, ram_total_mb: 0, ram_used_pct: 0, ssd: { total_gb: 0, used_gb: 0, used_pct: 0 }, hdd: { total_gb: 0, used_gb: 0, used_pct: 0 } },
  downloads: [] as unknown[],
}

async function fetchStatus() {
  try {
    const data = await api.get("/api/homeserver/status")
    return data.data as { services: Service[]; system: SystemStats; downloads: unknown[] }
  } catch {
    return FALLBACK
  }
}

function Bar({ pct }: { pct: number }) {
  return (
    <div className="w-full h-3 rounded-full bg-white/10 overflow-hidden">
      <div className="h-full rounded-full bg-white/30 transition-all" style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  )
}

export default function ServerStatusWidget() {
  const { data } = useQuery({
    queryKey: ["kiosk-server"],
    queryFn: fetchStatus,
    refetchInterval: 30_000,
  })

  if (!data) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="w-6 h-6 animate-spin opacity-40" /></div>
  }

  const s = data.system
  const services = data.services ?? []

  return (
    <div className="flex flex-col h-full gap-3">
      {/* System stats in a single horizontal row */}
      <div className="grid grid-cols-4 gap-x-4 gap-y-1 text-sm">
        {[
          { label: "CPU", pct: s.cpu_usage },
          { label: "RAM", pct: s.ram_used_pct },
          { label: "SSD", pct: s.ssd?.used_pct ?? 0 },
          { label: "HDD", pct: s.hdd?.used_pct ?? 0 },
        ].map((item) => (
          <div key={item.label} className="flex items-center gap-2">
            <span className="w-10 shrink-0 opacity-60">{item.label}</span>
            <Bar pct={item.pct} />
            <span className="w-10 shrink-0 text-right tabular-nums">{item.pct}%</span>
          </div>
        ))}
      </div>

      {/* Services with names */}
      <div className="flex-1 grid grid-cols-5 content-center gap-x-4 gap-y-2">
        {services.map((svc) => (
          <div key={svc.port} className="flex items-center gap-2">
            <span className="text-lg shrink-0">{svc.icon}</span>
            <span className="text-sm truncate flex-1">{svc.name}</span>
            <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${svc.up ? "bg-green-400" : "bg-red-400"}`} />
          </div>
        ))}
      </div>
    </div>
  )
}
