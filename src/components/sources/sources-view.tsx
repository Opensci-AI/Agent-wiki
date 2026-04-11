import { useState, useEffect, useCallback, useRef } from "react"
import { Plus, FileText, RefreshCw, BookOpen, Trash2, Globe, Loader2, AlertCircle, CheckCircle2, Clock, Sparkles, Eye, ChevronDown, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
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
import { ScrollArea } from "@/components/ui/scroll-area"
import { useWikiStore, type ActiveTask } from "@/stores/wiki-store"
import { sources as sourcesApi, type Source } from "@/api/sources"
import { pages as pagesApi, type WikiPage } from "@/api/pages"
import { ingest, tasks, type TaskStatus } from "@/api/ingest"
import { useTranslation } from "react-i18next"
import { WebClipDialog } from "./web-clip-dialog"
import { toast } from "sonner"

export function SourcesView() {
  const { t } = useTranslation()
  const project = useWikiStore((s) => s.project)
  const setActiveView = useWikiStore((s) => s.setActiveView)
  const setChatExpanded = useWikiStore((s) => s.setChatExpanded)
  const bumpDataVersion = useWikiStore((s) => s.bumpDataVersion)
  const activeTasks = useWikiStore((s) => s.activeTasks)
  const setActiveTask = useWikiStore((s) => s.setActiveTask)
  const updateActiveTask = useWikiStore((s) => s.updateActiveTask)
  const [sourcesList, setSourcesList] = useState<Source[]>([])
  const [importing, setImporting] = useState(false)
  const [sourceToDelete, setSourceToDelete] = useState<Source | null>(null)
  const [showWebClip, setShowWebClip] = useState(false)
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set())
  const [sourcePages, setSourcePages] = useState<Map<string, WikiPage[]>>(new Map())
  const [pageToDelete, setPageToDelete] = useState<WikiPage | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollingRef = useRef<Set<string>>(new Set()) // Track which tasks are being polled
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)

  const loadSources = useCallback(async () => {
    if (!project?.id) return
    try {
      const list = await sourcesApi.list(project.id)
      setSourcesList(list)
    } catch {
      setSourcesList([])
    }
  }, [project])

  // Load pages related to a source
  const loadSourcePages = useCallback(async (sourceFilename: string) => {
    if (!project?.id) return
    try {
      const relatedPages = await pagesApi.related(project.id, sourceFilename)
      setSourcePages(prev => new Map(prev).set(sourceFilename, relatedPages))
    } catch (err) {
      console.error("Failed to load related pages:", err)
    }
  }, [project])

  // Toggle expand/collapse for a source
  const toggleSourceExpand = useCallback((source: Source) => {
    const filename = source.original_name
    setExpandedSources(prev => {
      const next = new Set(prev)
      if (next.has(filename)) {
        next.delete(filename)
      } else {
        next.add(filename)
        // Load pages when expanding
        if (!sourcePages.has(filename)) {
          loadSourcePages(filename)
        }
      }
      return next
    })
  }, [sourcePages, loadSourcePages])

  // Delete a wiki page
  const handleDeletePage = async () => {
    if (!project?.id || !pageToDelete) return
    try {
      await pagesApi.delete(project.id, pageToDelete.id)
      // Refresh pages for all expanded sources
      expandedSources.forEach(filename => loadSourcePages(filename))
      bumpDataVersion()
      toast.success(`Đã xoá "${pageToDelete.title}"`)
    } catch (err) {
      console.error("Failed to delete page:", err)
      toast.error(`Không thể xoá: ${err}`)
    } finally {
      setPageToDelete(null)
    }
  }

  useEffect(() => {
    loadSources()
  }, [loadSources])

  async function handleImport() {
    // Use native file input instead of Tauri dialog
    fileInputRef.current?.click()
  }

  async function handleFilesSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0 || !project?.id) return

    setImporting(true)
    for (const file of Array.from(files)) {
      try {
        const uploaded = await sourcesApi.upload(project.id, file)
        await loadSources() // Refresh to show new file

        // Auto-process based on status
        if (uploaded.status === "uploaded") {
          // Needs extraction (images, scanned PDFs) - start extraction then ingest
          await startFullPipeline(uploaded)
        } else if (uploaded.status === "ready") {
          // Already extracted (text docs) - start ingest directly
          await handleIngest(uploaded)
        }
      } catch (err) {
        console.error(`Failed to import ${file.name}:`, err)
        toast.error(`Failed to upload ${file.name}`)
      }
    }
    setImporting(false)
    // Reset input so same file can be selected again
    e.target.value = ""
    bumpDataVersion()
  }

  // Resume polling for any active tasks when component mounts
  useEffect(() => {
    if (!project?.id) return

    // Resume polling for tasks that aren't already being polled
    activeTasks.forEach((task, sourceId) => {
      if (!pollingRef.current.has(sourceId) && task.status !== "completed" && task.status !== "failed") {
        startPolling(sourceId, task.taskId, task.type)
      }
    })
  }, [project?.id, activeTasks.size])

  // Start polling a task
  function startPolling(sourceId: string, taskId: string, type: "extract" | "ingest", onComplete?: () => void) {
    if (!project?.id || pollingRef.current.has(sourceId)) return

    pollingRef.current.add(sourceId)

    const poll = async () => {
      if (!pollingRef.current.has(sourceId)) return // Stopped

      try {
        const status = await tasks.status(project.id!, taskId)
        updateActiveTask(sourceId, {
          status: status.status,
          statusDetail: status.status_detail,
          progress: status.progress_pct,
        })

        if (status.status === "completed") {
          pollingRef.current.delete(sourceId)
          setTimeout(() => {
            setActiveTask(sourceId, null)
            loadSources()
            bumpDataVersion()
            if (onComplete) onComplete()
          }, 500)
          return
        }

        if (status.status === "failed") {
          pollingRef.current.delete(sourceId)
          setActiveTask(sourceId, null)
          toast.error(status.error || "Task failed")
          return
        }

        setTimeout(poll, 1000)
      } catch {
        pollingRef.current.delete(sourceId)
        setActiveTask(sourceId, null)
      }
    }

    poll()
  }

  // Full pipeline: Extract → Ingest
  async function startFullPipeline(source: Source) {
    if (!project?.id || activeTasks.has(source.id)) return

    try {
      // Step 1: Start extraction
      const extractTask = await sourcesApi.extract(project.id, source.id) as TaskStatus
      setActiveTask(source.id, {
        sourceId: source.id,
        taskId: extractTask.id,
        type: "extract",
        status: extractTask.status,
        statusDetail: extractTask.status_detail,
        progress: extractTask.progress_pct,
      })

      // Poll extraction and then auto-start ingest when done
      startPolling(source.id, extractTask.id, "extract", async () => {
        // Extraction complete - refresh source and start ingest
        await loadSources()
        const updatedSources = await sourcesApi.list(project.id!)
        const updatedSource = updatedSources.find(s => s.id === source.id)
        if (updatedSource && updatedSource.status === "ready") {
          // Small delay to let user see extraction complete
          setTimeout(() => handleIngest(updatedSource), 500)
        }
      })
    } catch (err: any) {
      console.error("Failed to start extraction:", err)
      const message = err?.body || err?.message || "Unknown error"
      toast.error(`Failed to start extraction: ${message}`)
    }
  }

  async function handleConfirmDelete() {
    if (!project?.id || !sourceToDelete) return
    try {
      await sourcesApi.delete(project.id, sourceToDelete.id)
      await loadSources()
      bumpDataVersion()
      toast.success(t("sources.deleted", { name: sourceToDelete.original_name }) || `Deleted "${sourceToDelete.original_name}"`)
    } catch (err) {
      console.error("Failed to delete source:", err)
      toast.error(`Failed to delete: ${err}`)
    } finally {
      setSourceToDelete(null)
    }
  }

  async function handleExtract(source: Source) {
    if (!project?.id || activeTasks.has(source.id)) return
    try {
      const task = await sourcesApi.extract(project.id, source.id) as TaskStatus
      setActiveTask(source.id, {
        sourceId: source.id,
        taskId: task.id,
        type: "extract",
        status: task.status,
        statusDetail: task.status_detail,
        progress: task.progress_pct,
      })
      startPolling(source.id, task.id, "extract", () => {
        toast.success(`Text extracted from ${source.original_name}`)
      })
    } catch (err: any) {
      console.error("Failed to start extraction:", err)
      const message = err?.body || err?.message || "Unknown error"
      toast.error(`Failed to start extraction: ${message}`)
    }
  }

  async function handleIngest(source: Source) {
    if (!project?.id || activeTasks.has(source.id)) return
    try {
      const task = await ingest.start(project.id, source.id)
      setActiveTask(source.id, {
        sourceId: source.id,
        taskId: task.id,
        type: "ingest",
        status: task.status,
        statusDetail: task.status_detail,
        progress: task.progress_pct,
      })
      startPolling(source.id, task.id, "ingest", () => {
        toast.success(`Đã tạo wiki pages từ ${source.original_name}`)
        // Auto-expand to show generated pages
        setExpandedSources(prev => new Set(prev).add(source.original_name))
        loadSourcePages(source.original_name)
      })
    } catch (err: any) {
      console.error("Failed to start ingest:", err)
      const message = err?.body || err?.message || "Unknown error"
      toast.error(`Failed to start wiki generation: ${message}`)
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Hidden file input for browser file picker */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        accept=".md,.mdx,.txt,.rtf,.pdf,.html,.htm,.xml,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.json,.jsonl,.csv,.tsv,.yaml,.yml,.py,.js,.ts,.jsx,.tsx,.rs,.go,.java,.png,.jpg,.jpeg,.gif,.webp,.svg"
        onChange={handleFilesSelected}
      />

      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{t("sources.title")}</h2>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={loadSources} title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowWebClip(true)}>
            <Globe className="mr-1 h-4 w-4" />
            Clip
          </Button>
          <Button size="sm" onClick={handleImport} disabled={importing}>
            <Plus className="mr-1 h-4 w-4" />
            {importing ? t("sources.importing") : t("sources.import")}
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        {sourcesList.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 p-8 text-center text-sm text-muted-foreground">
            <p>{t("sources.noSources")}</p>
            <p>{t("sources.importHint")}</p>
            <Button variant="outline" size="sm" onClick={handleImport}>
              <Plus className="mr-1 h-4 w-4" />
              {t("sources.importFiles")}
            </Button>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {sourcesList.map((source) => {
              const activeTask = activeTasks.get(source.id)
              const isProcessing = !!activeTask
              const needsExtraction = source.status === "uploaded"
              const isReady = source.status === "ready"
              const isIngested = source.status === "ingested"
              const isExpanded = expandedSources.has(source.original_name)
              const relatedPages = sourcePages.get(source.original_name) || []

              return (
                <div
                  key={source.id}
                  className="rounded-md border bg-card text-sm"
                >
                  {/* Header row */}
                  <div className="flex items-center gap-2 p-2 hover:bg-accent/50 transition-colors">
                    {/* Expand/collapse toggle */}
                    <button
                      onClick={() => toggleSourceExpand(source)}
                      className="shrink-0 text-muted-foreground hover:text-foreground"
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </button>
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="flex-1 truncate font-medium">{source.original_name}</span>

                    {/* Status badge */}
                    {isProcessing ? (
                      <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-600">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Đang xử lý
                      </span>
                    ) : needsExtraction ? (
                      <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-600">
                        <Clock className="h-3 w-3" />
                        Cần OCR
                      </span>
                    ) : isIngested ? (
                      <span className="flex items-center gap-1 rounded-full bg-purple-500/10 px-2 py-0.5 text-[10px] font-medium text-purple-600">
                        <CheckCircle2 className="h-3 w-3" />
                        Đã tạo Wiki
                      </span>
                    ) : isReady ? (
                      <span className="flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-[10px] font-medium text-green-600">
                        <CheckCircle2 className="h-3 w-3" />
                        Sẵn sàng
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 rounded-full bg-gray-500/10 px-2 py-0.5 text-[10px] font-medium text-gray-600">
                        {source.status}
                      </span>
                    )}

                    {/* Action buttons */}
                    {!isProcessing && (
                      <>
                        {needsExtraction ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 px-2 text-xs"
                            title="Trích xuất văn bản bằng OCR"
                            onClick={() => handleExtract(source)}
                          >
                            <Sparkles className="mr-1 h-3 w-3" />
                            Trích xuất
                          </Button>
                        ) : isReady || isIngested ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 px-2 text-xs"
                            title="Tạo các trang wiki từ nguồn này"
                            onClick={() => handleIngest(source)}
                          >
                            <BookOpen className="mr-1 h-3 w-3" />
                            {isIngested ? "Tạo lại" : "Tạo Wiki"}
                          </Button>
                        ) : null}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive"
                          title={t("sources.delete")}
                          onClick={() => setSourceToDelete(source)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </>
                    )}
                  </div>

                  {/* Progress bar when processing */}
                  {isProcessing && activeTask && (
                    <div className="px-2 pb-2 space-y-1">
                      <Progress value={activeTask.progress} className="h-1.5" />
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                        <span className="truncate">
                          {activeTask.statusDetail || `${activeTask.type === "extract" ? "Đang trích xuất" : "Đang tạo wiki"}...`}
                        </span>
                        <span className="shrink-0 ml-2">{activeTask.progress}%</span>
                      </div>
                    </div>
                  )}

                  {/* Generated pages list */}
                  {isExpanded && (
                    <div className="border-t bg-muted/30 px-2 py-1.5">
                      {relatedPages.length === 0 ? (
                        <div className="text-xs text-muted-foreground py-2 text-center">
                          {isIngested ? "Đang tải..." : "Chưa có trang wiki nào được tạo"}
                        </div>
                      ) : (
                        <div className="space-y-0.5">
                          <div className="text-[10px] font-medium text-muted-foreground mb-1">
                            {relatedPages.length} trang đã tạo:
                          </div>
                          {relatedPages.map((page) => (
                            <div
                              key={page.id}
                              className="flex items-center gap-1.5 rounded px-1.5 py-1 hover:bg-accent/50 group"
                            >
                              <BookOpen className="h-3 w-3 shrink-0 text-primary/70" />
                              <button
                                className="flex-1 text-left text-xs truncate hover:text-primary"
                                onClick={() => setSelectedPageId(page.id)}
                                title={`Xem: ${page.title}`}
                              >
                                {page.title}
                              </button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-primary"
                                title="Xem nội dung"
                                onClick={() => setSelectedPageId(page.id)}
                              >
                                <Eye className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                                title="Xoá trang"
                                onClick={() => setPageToDelete(page)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </ScrollArea>

      <div className="border-t px-4 py-2 text-xs text-muted-foreground">
        {t("sources.sourceCount", { count: sourcesList.length })}
      </div>

      {project?.id && (
        <WebClipDialog
          open={showWebClip}
          onOpenChange={setShowWebClip}
          projectId={project.id}
          onClipped={() => { loadSources(); bumpDataVersion() }}
        />
      )}

      {/* Delete source dialog */}
      <AlertDialog open={!!sourceToDelete} onOpenChange={(open) => !open && setSourceToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xoá nguồn?</AlertDialogTitle>
            <AlertDialogDescription>
              Thao tác này sẽ xoá vĩnh viễn "{sourceToDelete?.original_name}" và không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Huỷ</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Xoá
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete page dialog */}
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
    </div>
  )
}
