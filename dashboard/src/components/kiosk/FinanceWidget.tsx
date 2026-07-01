import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { api } from "../../api/client"
import AnimatedNumber from "./AnimatedNumber"
import type { FinanceSummary } from "../../types"

const FALLBACK: FinanceSummary = { income: 3200, expense: 1850, balance: 1350 }

async function fetchFinance(): Promise<FinanceSummary> {
  try {
    const data = await api.get("/api/finance/summary")
    if (data.data?.income != null) return data.data
    return { income: 0, expense: 0, balance: 0 }
  } catch { return FALLBACK }
}

export default function FinanceWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ["kiosk-finance"],
    queryFn: fetchFinance,
    refetchInterval: 60_000,
  })

  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin text-purple-400 mx-auto mt-6" />

  const s = data ?? FALLBACK
  const diff = s.income - s.expense
  const ratio = s.income > 0 ? Math.min(s.expense / s.income, 1) : 0

  return (
    <div className="flex flex-col justify-center h-full gap-1">
      <div className="flex items-baseline gap-2">
        <span className="text-4xl font-light shrink-0">
          <AnimatedNumber value={s.balance} />
        </span>
        <span className="text-base opacity-40">RON</span>
        <span className="text-sm opacity-40 ml-auto shrink-0">
          {diff > 0 ? `+${diff}` : diff}
        </span>
      </div>

      <div className="flex items-center gap-3 text-base">
        <span className="opacity-60">+<AnimatedNumber value={s.income} /></span>
        <span className="opacity-30">/</span>
        <span className="opacity-60">-<AnimatedNumber value={s.expense} /></span>
      </div>

      <div className="w-full h-3 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full bg-white/30 transition-all" style={{ width: `${ratio * 100}%` }} />
      </div>
    </div>
  )
}
