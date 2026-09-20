import { useState, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { fetchNews } from "../api/queries/news"
import { Card } from "../components/ui/Card"
import { Spinner } from "../components/ui/Spinner"
import { Input } from "../components/ui/Input"
import {
  Newspaper,
  ExternalLink,
  Globe,
  TrendingUp,
  Cpu,
  Sparkles,
  RefreshCw,
  Search,
  Clock,
  Landmark,
} from "lucide-react"
import type { NewsArticle } from "../types"

const CATEGORIES = [
  { id: "all", label: "Toate", icon: Globe },
  { id: "romania", label: "România", icon: Landmark },
  { id: "business", label: "Economie", icon: TrendingUp },
  { id: "tech", label: "Tehnologie", icon: Cpu },
  { id: "ai", label: "Inteligență Artificială", icon: Sparkles },
  { id: "world", label: "Internațional", icon: Newspaper },
]

export default function News() {
  const [activeCat, setActiveCat] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")

  const { data: articles, isLoading, isFetching, refetch } = useQuery<NewsArticle[]>({
    queryKey: ["news", activeCat],
    queryFn: () => fetchNews(activeCat, 30),
    refetchInterval: 180_000, // 3 mins auto-refresh
  })

  const filteredArticles = useMemo(() => {
    if (!articles) return []
    if (!searchQuery.trim()) return articles
    const q = searchQuery.toLowerCase()
    return articles.filter(
      (a) =>
        a.title.toLowerCase().includes(q) ||
        a.source.toLowerCase().includes(q) ||
        a.category_title.toLowerCase().includes(q)
    )
  }, [articles, searchQuery])

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">Știri Live</h1>
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </div>
          <p className="text-text-secondary text-sm">
            Flux de știri în timp real din presa românească și internațională
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative w-full sm:w-60">
            <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Caută în știri..."
              className="pl-9 text-xs h-9"
            />
          </div>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-2 rounded-xl bg-surface border border-border text-text-secondary hover:text-text-primary transition-all disabled:opacity-50 shrink-0"
            title="Actualizează fluxul"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin text-primary" : ""}`} />
          </button>
        </div>
      </div>

      {/* Category Filter Pills */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
        {CATEGORIES.map((c) => {
          const Icon = c.icon
          const isActive = activeCat === c.id
          return (
            <button
              key={c.id}
              onClick={() => setActiveCat(c.id)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all ${
                isActive
                  ? "bg-primary text-white shadow-sm font-semibold"
                  : "bg-surface/80 text-text-secondary hover:text-text-primary border border-border/50"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {c.label}
            </button>
          )
        })}
      </div>

      {/* Articles Grid / List */}
      {isLoading ? (
        <Spinner className="py-16" />
      ) : !filteredArticles.length ? (
        <Card>
          <div className="py-12 text-center space-y-2">
            <Newspaper className="w-8 h-8 text-text-muted mx-auto" />
            <p className="text-sm text-text-muted">
              {searchQuery ? "Nicio știre nu corespunde căutării." : "Nu s-au putut prelua știrile în acest moment."}
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <AnimatePresence>
            {filteredArticles.map((article, index) => (
              <motion.a
                key={article.id || index}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.03, 0.3) }}
                className="group block"
              >
                <Card className="h-full flex flex-col justify-between p-5 sm:p-6 hover:border-border/80 group-hover:bg-white/[0.04] transition-all">
                  <div>
                    {/* Top row: Category badge, source, time */}
                    <div className="flex items-center justify-between gap-2 mb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs px-2 py-0.5 rounded-md bg-primary/10 text-primary font-medium">
                          {article.category_title || article.category}
                        </span>
                        <span className="text-xs font-semibold text-text-secondary truncate max-w-[120px]">
                          {article.source}
                        </span>
                      </div>

                      <div className="flex items-center gap-1 text-[11px] text-text-muted shrink-0 font-mono">
                        <Clock className="w-3 h-3" />
                        <span>{article.relative_time}</span>
                      </div>
                    </div>

                    {/* Headline */}
                    <h3 className="text-sm font-semibold text-text-primary leading-snug group-hover:text-primary transition-colors line-clamp-3">
                      {article.title}
                    </h3>
                  </div>

                  {/* Read Article footer */}
                  <div className="flex items-center justify-end gap-1 text-xs text-text-muted group-hover:text-primary transition-colors pt-3 mt-3 border-t border-border/40">
                    <span className="text-[11px] font-medium">Citește articolul</span>
                    <ExternalLink className="w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  </div>
                </Card>
              </motion.a>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  )
}
