import { useEffect, useCallback, useRef } from "react"
import { X } from "lucide-react"
import { useWikiStore } from "@/stores/wiki-store"
import { pages } from "@/api/pages"
import { WikiEditor } from "@/components/editor/wiki-editor"
import { FilePreview } from "@/components/editor/file-preview"

export function PreviewPanel() {
  const project = useWikiStore((s) => s.project)
  const selectedPageId = useWikiStore((s) => s.selectedPageId)
  const selectedPage = useWikiStore((s) => s.selectedPage)
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)
  const setSelectedPage = useWikiStore((s) => s.setSelectedPage)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!selectedPageId || !project?.id) {
      setSelectedPage(null)
      return
    }

    pages.get(project.id, selectedPageId)
      .then(setSelectedPage)
      .catch((err) => {
        console.error("Failed to load page:", err)
        setSelectedPage(null)
      })
  }, [selectedPageId, project, setSelectedPage])

  const handleSave = useCallback(
    (markdown: string) => {
      if (!selectedPageId || !project?.id) return
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        pages.update(project.id, selectedPageId, { content: markdown }).catch((err) =>
          console.error("Failed to save:", err)
        )
      }, 1000)
    },
    [selectedPageId, project]
  )

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  if (!selectedPage) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Select a page to preview
      </div>
    )
  }

  const isMarkdown = selectedPage.path.endsWith(".md") || selectedPage.type !== "binary"

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-3 py-1.5">
        <span className="truncate text-xs text-muted-foreground" title={selectedPage.path}>
          {selectedPage.title}
        </span>
        <button
          onClick={() => setSelectedPageId(null)}
          className="shrink-0 rounded p-1 text-muted-foreground hover:bg-accent"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="flex-1 min-w-0 overflow-auto">
        {isMarkdown ? (
          <WikiEditor
            key={selectedPageId}
            content={selectedPage.content}
            onSave={handleSave}
          />
        ) : (
          <FilePreview
            key={selectedPageId}
            filePath={selectedPage.path}
            textContent={selectedPage.content}
          />
        )}
      </div>
    </div>
  )
}
