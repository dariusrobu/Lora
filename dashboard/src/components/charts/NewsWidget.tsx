import { useQuery } from "@tanstack/react-query"
import { fetchNews } from "../../api/queries/news"
import { WidgetCard } from "./WidgetCard"
import { Newspaper, ExternalLink, Clock } from "lucide-react"

interface Props {
  onExpand?: () => void
}

export function NewsWidget({ onExpand }: Props) {
  const { data: articles, isLoading, isError, refetch } = useQuery({
    queryKey: ["news", "widget"],
    queryFn: () => fetchNews("all", 4),
    refetchInterval: 120_000,
    staleTime: 60_000,
  })

  const hasData = (articles?.length ?? 0) > 0

  return (
    <WidgetCard
      icon={<Newspaper className="w-4 h-4" />}
      label="Știri Live"
      linkTo="/news"
      onExpand={onExpand}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
      isEmpty={!hasData && !isLoading && !isError}
      emptyMessage="Flux de știri indisponibil"
    >
      <div className="space-y-2.5">
        {articles?.slice(0, 3).map((article, idx) => (
          <a
            key={article.id || idx}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-start justify-between gap-3 p-2 rounded-xl hover:bg-white/[0.04] transition-all border border-transparent hover:border-border/40"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-primary/15 text-primary font-semibold">
                  {article.category_title}
                </span>
                <span className="text-[10px] text-text-muted truncate max-w-[100px]">
                  {article.source}
                </span>
                <span className="text-[10px] text-text-muted ml-auto font-mono flex items-center gap-0.5 shrink-0">
                  <Clock className="w-2.5 h-2.5" />
                  {article.relative_time}
                </span>
              </div>
              <p className="text-xs font-medium text-text-primary group-hover:text-primary transition-colors line-clamp-2 leading-snug">
                {article.title}
              </p>
            </div>
            <ExternalLink className="w-3.5 h-3.5 text-text-muted group-hover:text-primary group-hover:translate-x-0.5 transition-all shrink-0 mt-2" />
          </a>
        ))}
      </div>
    </WidgetCard>
  )
}
