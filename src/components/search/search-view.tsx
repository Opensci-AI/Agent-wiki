import { useState, useEffect, useRef, useCallback } from "react"
import { Search, FileText } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useWikiStore } from "@/stores/wiki-store"
import { pages as pagesApi, type WikiPage } from "@/api/pages"
import { useTranslation } from "react-i18next"

interface SearchResult {
  page: WikiPage
  snippet: string
  titleMatch: boolean
}

export function SearchView() {
  const { t } = useTranslation()
  const project = useWikiStore((s) => s.project)
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)
  const setActiveView = useWikiStore((s) => s.setActiveView)

  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const doSearch = useCallback(
    async (q: string) => {
      if (!project?.id || !q.trim()) {
        setResults([])
        return
      }
      setSearching(true)
      try {
        const pages = await pagesApi.search(project.id, q.trim())
        const lower = q.toLowerCase()
        const found: SearchResult[] = pages.map((page) => {
          const titleMatch = page.title.toLowerCase().includes(lower)
          let snippet = ""
          if (page.content) {
            const idx = page.content.toLowerCase().indexOf(lower)
            if (idx !== -1) {
              const start = Math.max(0, idx - 50)
              const end = Math.min(page.content.length, idx + q.length + 100)
              snippet = (start > 0 ? "..." : "") + page.content.slice(start, end) + (end < page.content.length ? "..." : "")
            } else {
              snippet = page.content.slice(0, 150) + (page.content.length > 150 ? "..." : "")
            }
          }
          return { page, snippet, titleMatch }
        })
        found.sort((a, b) => (a.titleMatch === b.titleMatch ? 0 : a.titleMatch ? -1 : 1))
        setResults(found)
      } catch (err) {
        console.error("Search failed:", err)
        setResults([])
      } finally {
        setSearching(false)
      }
    },
    [project],
  )

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(query), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, doSearch])

  function handleOpen(result: SearchResult) {
    setSelectedPageId(result.page.id)
    setActiveView("wiki")
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b px-4 py-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("search.placeholder")}
            autoFocus
            className="w-full rounded-md border bg-background py-2 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <ScrollArea className="flex-1">
        {!query.trim() ? (
          <div className="flex flex-col items-center justify-center gap-2 p-8 text-center text-sm text-muted-foreground">
            <Search className="h-8 w-8 text-muted-foreground/30" />
            <p>{t("search.startSearching")}</p>
          </div>
        ) : searching ? (
          <div className="p-4 text-center text-sm text-muted-foreground">Searching...</div>
        ) : results.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            {t("search.noResults")} <span className="font-medium">"{query}"</span>
          </div>
        ) : (
          <div className="flex flex-col gap-1 p-2">
            <div className="px-2 py-1 text-xs text-muted-foreground">
              {results.length} result{results.length !== 1 ? "s" : ""}
            </div>
            {results.map((result) => (
              <SearchResultCard
                key={result.page.id}
                result={result}
                query={query}
                onClick={() => handleOpen(result)}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}

function SearchResultCard({
  result,
  query,
  onClick,
}: {
  result: SearchResult
  query: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-lg border p-3 text-left text-sm hover:bg-accent transition-colors"
    >
      <div className="flex items-start gap-2 mb-1.5">
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">
            <HighlightedText text={result.page.title} query={query} />
          </div>
          <div className="text-[11px] text-muted-foreground truncate">{result.page.path}</div>
        </div>
      </div>
      <p className="text-xs text-muted-foreground line-clamp-2">
        <HighlightedText text={result.snippet} query={query} />
      </p>
    </button>
  )
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>

  const regex = new RegExp(`(${escapeRegex(query)})`, "gi")
  const parts = text.split(regex)

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="bg-primary/20 text-primary rounded px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}
