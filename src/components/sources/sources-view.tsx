import { useState, useEffect, useCallback, useRef } from "react"
import { Plus, FileText, RefreshCw, BookOpen, Trash2, Globe, Loader2, AlertCircle, CheckCircle2, Clock, Sparkles } from "lucide-react"
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
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollingRef = useRef<Set<string>>(new Set()) // Track which tasks are being polled

  const loadSources = useCallback(async () => {
    if (!project?.id) return
    try {
      const list = await sourcesApi.list(project.id)
      setSourcesList(list)
    } catch {
      setSourcesList([])
    }
  }, [project])

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
        toast.success(`Wiki pages generated from ${source.original_name}`)
        setChatExpanded(true)
        setActiveView("wiki")
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

              return (
                <div
                  key={source.id}
                  className="rounded-md border bg-card p-2 text-sm transition-colors hover:bg-accent/50"
                >
                  {/* Header row */}
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="flex-1 truncate font-medium">{source.original_name}</span>

                    {/* Status badge */}
                    {isProcessing ? (
                      <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-600">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Processing
                      </span>
                    ) : needsExtraction ? (
                      <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-600">
                        <Clock className="h-3 w-3" />
                        Needs OCR
                      </span>
                    ) : isReady ? (
                      <span className="flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-[10px] font-medium text-green-600">
                        <CheckCircle2 className="h-3 w-3" />
                        Ready
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
                            title="Extract text using OCR"
                            onClick={() => handleExtract(source)}
                          >
                            <Sparkles className="mr-1 h-3 w-3" />
                            Extract
                          </Button>
                        ) : isReady ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 px-2 text-xs"
                            title="Generate wiki pages from this source"
                            onClick={() => handleIngest(source)}
                          >
                            <BookOpen className="mr-1 h-3 w-3" />
                            Generate Wiki
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
                    <div className="mt-2 space-y-1">
                      <Progress value={activeTask.progress} className="h-1.5" />
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                        <span className="truncate">
                          {activeTask.statusDetail || `${activeTask.type === "extract" ? "Extracting" : "Generating"}...`}
                        </span>
                        <span className="shrink-0 ml-2">{activeTask.progress}%</span>
                      </div>
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

      <AlertDialog open={!!sourceToDelete} onOpenChange={(open) => !open && setSourceToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("sources.deleteTitle") || "Delete source?"}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("sources.deleteConfirm", { name: sourceToDelete?.original_name }) ||
                `This will permanently delete "${sourceToDelete?.original_name}" and cannot be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel") || "Cancel"}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {t("common.delete") || "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
