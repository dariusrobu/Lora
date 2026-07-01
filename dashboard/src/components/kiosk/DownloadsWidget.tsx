import { useQuery } from "@tanstack/react-query"
import { ArrowDown } from "lucide-react"
import { api } from "../../api/client"

interface Torrent {
  name: string
  progress: number
  dlspeed: number
  eta: number
  downloaded: number
  total_size: number
  state: string
}

function fmtSize(bytes: number): string {
  if (bytes >= 1 << 30) return (bytes / (1 << 30)).toFixed(1) + " GB"
  if (bytes >= 1 << 20) return (bytes / (1 << 20)).toFixed(0) + " MB"
  return (bytes / (1 << 10)).toFixed(0) + " KB"
}

function fmtSpeed(bytesPerSec: number): string {
  if (bytesPerSec >= 1 << 20) return (bytesPerSec / (1 << 20)).toFixed(1) + " MB/s"
  if (bytesPerSec >= 1 << 10) return (bytesPerSec / (1 << 10)).toFixed(0) + " KB/s"
  return "0 B/s"
}

function fmtEta(sec: number): string {
  if (sec <= 0 || sec === 8640000) return "—"
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

async function fetchDownloads() {
  try {
    const data = await api.get("/api/homeserver/status")
    return (data.data as { downloads: Torrent[] }).downloads ?? []
  } catch {
    return []
  }
}

export default function DownloadsWidget() {
  const { data: downloads } = useQuery({
    queryKey: ["kiosk-server"],
    queryFn: fetchDownloads,
    refetchInterval: 30_000,
  })

  const list = downloads ?? []
  const top = list[0]

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-1">
        <ArrowDown className="w-6 h-6" />
        <span className="text-5xl font-light">{list.length}</span>
        <span className="text-base opacity-60">active</span>
      </div>

      {top ? (
        <div className="flex-1 flex flex-col justify-center min-h-0">
          <div className="text-base truncate opacity-80 mb-1">{top.name}</div>
          <div className="w-full h-3 rounded-full bg-white/10 overflow-hidden mb-1">
            <div className="h-full rounded-full bg-white/30 transition-all" style={{ width: `${top.progress}%` }} />
          </div>
          <div className="flex justify-between text-sm opacity-50">
            <span>{top.progress}%</span>
            <span className="truncate ml-2 text-right">{top.progress < 100 ? `${fmtSpeed(top.dlspeed)} / ${fmtEta(top.eta)}` : "Finalizat"}</span>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-base opacity-40">
          Nici o descărcare
        </div>
      )}
    </div>
  )
}
