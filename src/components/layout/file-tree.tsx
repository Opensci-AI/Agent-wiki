import { FileText } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useWikiStore } from "@/stores/wiki-store"

export function FileTree() {
  const wikiPages = useWikiStore((s) => s.pages)
  const project = useWikiStore((s) => s.project)
  const selectedPageId = useWikiStore((s) => s.selectedPageId)
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)

  if (!project) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-muted-foreground">
        No project open
      </div>
    )
  }

  return (
    <ScrollArea className="h-full min-w-0 overflow-hidden">
      <div className="p-2">
        <div className="mb-2 px-2 text-xs font-semibold uppercase text-muted-foreground">
          {project.name}
        </div>
        {wikiPages.length === 0 ? (
          <div className="px-2 py-4 text-center text-xs text-muted-foreground">
            No pages yet
          </div>
        ) : (
          wikiPages.map((page) => {
            const isSelected = selectedPageId === page.id
            return (
              <button
                key={page.id}
                onClick={() => setSelectedPageId(page.id)}
                className={`flex w-full items-center gap-1 py-1 text-sm ${
                  isSelected
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
                }`}
                style={{ paddingLeft: 26 }}
              >
                <FileText className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{page.title || page.path}</span>
              </button>
            )
          })
        )}
      </div>
    </ScrollArea>
  )
}
