import { useEffect, useCallback, useRef, useState } from "react"
import { X, Trash2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
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
import { pages } from "@/api/pages"
import { WikiEditor } from "@/components/editor/wiki-editor"
import { FilePreview } from "@/components/editor/file-preview"
import { toast } from "sonner"

export function PreviewPanel() {
  const project = useWikiStore((s) => s.project)
  const selectedPageId = useWikiStore((s) => s.selectedPageId)
  const selectedPage = useWikiStore((s) => s.selectedPage)
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)
  const setSelectedPage = useWikiStore((s) => s.setSelectedPage)
  const bumpDataVersion = useWikiStore((s) => s.bumpDataVersion)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

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
      setIsSaving(true)
      saveTimerRef.current = setTimeout(() => {
        pages.update(project.id, selectedPageId, { content: markdown })
          .then(() => setIsSaving(false))
          .catch((err) => {
            console.error("Failed to save:", err)
            setIsSaving(false)
            toast.error("Không thể lưu thay đổi")
          })
      }, 1000)
    },
    [selectedPageId, project]
  )

  const handleDelete = useCallback(async () => {
    if (!selectedPageId || !project?.id) return
    try {
      await pages.delete(project.id, selectedPageId)
      toast.success("Đã xoá trang")
      setSelectedPageId(null)
      bumpDataVersion()
    } catch (err) {
      console.error("Failed to delete:", err)
      toast.error("Không thể xoá trang")
    } finally {
      setShowDeleteDialog(false)
    }
  }, [selectedPageId, project, setSelectedPageId, bumpDataVersion])

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
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="truncate text-xs font-medium" title={selectedPage.path}>
            {selectedPage.title}
          </span>
          {isSaving && (
            <span className="text-[10px] text-muted-foreground flex items-center gap-1">
              <Save className="h-3 w-3 animate-pulse" />
              Đang lưu...
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-muted-foreground hover:text-destructive"
            title="Xoá trang"
            onClick={() => setShowDeleteDialog(true)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          <button
            onClick={() => setSelectedPageId(null)}
            className="rounded p-1 text-muted-foreground hover:bg-accent"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
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

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xoá trang wiki?</AlertDialogTitle>
            <AlertDialogDescription>
              Thao tác này sẽ xoá vĩnh viễn trang "{selectedPage?.title}" và không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Huỷ</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Xoá
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
