import { useState, useEffect } from "react"
import {
  FileText, Users, Lightbulb, BookOpen, HelpCircle, GitMerge, BarChart3, ChevronRight, ChevronDown, Layout, Globe, Plus, Trash2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { useWikiStore } from "@/stores/wiki-store"
import { sources as sourcesApi } from "@/api/sources"
import { pages as pagesApi, type WikiPage } from "@/api/pages"
import { CreatePageDialog } from "@/components/editor/create-page-dialog"
import type { Source } from "@/api/sources"
import { toast } from "sonner"

const TYPE_CONFIG: Record<string, { icon: typeof FileText; label: string; color: string; order: number }> = {
  overview:    { icon: Layout,      label: "Overview",     color: "text-primary", order: 0 },
  entity:      { icon: Users,       label: "Entities",     color: "text-primary",   order: 1 },
  concept:     { icon: Lightbulb,   label: "Concepts",     color: "text-primary", order: 2 },
  source:      { icon: BookOpen,    label: "Sources",      color: "text-primary", order: 3 },
  synthesis:   { icon: GitMerge,    label: "Synthesis",    color: "text-primary",    order: 4 },
  comparison:  { icon: BarChart3,   label: "Comparisons",  color: "text-primary",order: 5 },
  query:       { icon: HelpCircle,  label: "Queries",      color: "text-primary",  order: 6 },
}

const DEFAULT_CONFIG = { icon: FileText, label: "Other", color: "text-muted-foreground", order: 99 }

export function KnowledgeTree() {
  const project = useWikiStore((s) => s.project)
  const selectedPageId = useWikiStore((s) => s.selectedPageId)
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)
  const wikiPages = useWikiStore((s) => s.pages)
  const bumpDataVersion = useWikiStore((s) => s.bumpDataVersion)
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set(["overview", "entity", "concept", "source"]))
  const [showCreatePage, setShowCreatePage] = useState(false)
  const [pageToDelete, setPageToDelete] = useState<WikiPage | null>(null)

  const handleDeletePage = async () => {
    if (!project?.id || !pageToDelete) return
    try {
      await pagesApi.delete(project.id, pageToDelete.id)
      if (selectedPageId === pageToDelete.id) {
        setSelectedPageId(null)
      }
      bumpDataVersion()
      toast.success(`Đã xoá "${pageToDelete.title}"`)
    } catch (err) {
      console.error("Failed to delete page:", err)
      toast.error("Không thể xoá trang")
    } finally {
      setPageToDelete(null)
    }
  }

  if (!project) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-muted-foreground">
        No project open
      </div>
    )
  }

  // Group pages by type
  const grouped = new Map<string, WikiPage[]>()
  for (const page of wikiPages) {
    const type = page.type || "other"
    const list = grouped.get(type) ?? []
    list.push(page)
    grouped.set(type, list)
  }

  // Sort groups by configured order
  const sortedGroups = [...grouped.entries()].sort((a, b) => {
    const orderA = TYPE_CONFIG[a[0]]?.order ?? DEFAULT_CONFIG.order
    const orderB = TYPE_CONFIG[b[0]]?.order ?? DEFAULT_CONFIG.order
    return orderA - orderB
  })

  function toggleType(type: string) {
    setExpandedTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-2">
        <div className="mb-2 flex items-center justify-between px-2">
          <span className="text-xs font-semibold uppercase text-muted-foreground">
            {project.name}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            title="Create new page"
            onClick={() => setShowCreatePage(true)}
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>

        {sortedGroups.length === 0 && (
          <div className="px-2 py-4 text-center text-xs text-muted-foreground">
            No wiki pages yet. Import sources to get started.
          </div>
        )}

        {sortedGroups.map(([type, items]) => {
          const config = TYPE_CONFIG[type] ?? DEFAULT_CONFIG
          const Icon = config.icon
          const isExpanded = expandedTypes.has(type)

          return (
            <div key={type} className="mb-1">
              <button
                onClick={() => toggleType(type)}
                className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm hover:bg-accent/50"
              >
                {isExpanded ? (
                  <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
                <Icon className={`h-3.5 w-3.5 shrink-0 ${config.color}`} />
                <span className="flex-1 text-left font-medium">{config.label}</span>
                <span className="text-xs text-muted-foreground">{items.length}</span>
              </button>

              {isExpanded && (
                <div className="ml-3">
                  {items.map((page) => {
                    const isSelected = selectedPageId === page.id
                    return (
                      <div
                        key={page.id}
                        className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-sm group ${
                          isSelected
                            ? "bg-accent text-accent-foreground"
                            : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
                        }`}
                      >
                        <button
                          onClick={() => setSelectedPageId(page.id)}
                          className="flex-1 flex items-center gap-1.5 text-left min-w-0"
                          title={page.path}
                        >
                          {page.frontmatter?.origin === "web-clip" && <Globe className="h-3 w-3 shrink-0 text-primary" />}
                          <span className="truncate">{page.title}</span>
                        </button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                          title="Xoá trang"
                          onClick={(e) => {
                            e.stopPropagation()
                            setPageToDelete(page)
                          }}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}

        {/* Raw sources quick access */}
        <RawSourcesSection />
      </div>

      <CreatePageDialog open={showCreatePage} onOpenChange={setShowCreatePage} />

      <AlertDialog open={!!pageToDelete} onOpenChange={(open) => !open && setPageToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xoá trang wiki?</AlertDialogTitle>
            <AlertDialogDescription>
              Thao tác này sẽ xoá vĩnh viễn trang "{pageToDelete?.title}" và không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Huỷ</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeletePage}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Xoá
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ScrollArea>
  )
}

function RawSourcesSection() {
  const project = useWikiStore((s) => s.project)
  const [expanded, setExpanded] = useState(false)
  const [rawSources, setRawSources] = useState<Source[]>([])

  useEffect(() => {
    if (!project?.id) return
    sourcesApi.list(project.id)
      .then((list) => setRawSources(list))
      .catch(() => setRawSources([]))
  }, [project])

  if (rawSources.length === 0) return null

  return (
    <div className="mt-2 border-t pt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm hover:bg-accent/50"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <BookOpen className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span className="flex-1 text-left font-medium text-muted-foreground">Raw Sources</span>
        <span className="text-xs text-muted-foreground">{rawSources.length}</span>
      </button>
      {expanded && (
        <div className="ml-3">
          {rawSources.map((source) => {
            // Sources don't have page IDs, so we can't directly select them the same way
            // For now, show them as informational items
            return (
              <div
                key={source.id}
                className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-sm text-muted-foreground"
              >
                <span className="truncate">{source.original_name}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

