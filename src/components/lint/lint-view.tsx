import { useState, useCallback } from "react"
import {
  Link2Off,
  Unlink,
  ArrowUpRight,
  AlertTriangle,
  Info,
  RefreshCw,
  CheckCircle2,
  FileX,
  FileQuestion,
  Wrench,
  Trash2,
} from "lucide-react"
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
import { useReviewStore } from "@/stores/review-store"
import { pages as pagesApi, lint as lintApi, type LintIssue } from "@/api/pages"
import { toast } from "sonner"

const SEVERITY_MAP: Record<string, "warning" | "info"> = {
  broken_wikilink: "warning",
  empty_page: "warning",
  missing_title: "warning",
  orphan_page: "info",
}

const typeConfig: Record<string, { icon: typeof AlertTriangle; label: string }> = {
  broken_wikilink: { icon: Link2Off, label: "Broken Link" },
  empty_page: { icon: FileX, label: "Empty Page" },
  missing_title: { icon: FileQuestion, label: "Missing Title" },
  orphan_page: { icon: Unlink, label: "Orphan Page" },
}

export function LintView() {
  const project = useWikiStore((s) => s.project)
  const wikiPages = useWikiStore((s) => s.pages)
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)
  const setActiveView = useWikiStore((s) => s.setActiveView)
  const bumpDataVersion = useWikiStore((s) => s.bumpDataVersion)

  const [results, setResults] = useState<LintIssue[]>([])
  const [running, setRunning] = useState(false)
  const [hasRun, setHasRun] = useState(false)
  const [fixingId, setFixingId] = useState<string | null>(null)
  const [orphanToDelete, setOrphanToDelete] = useState<{ issue: LintIssue; index: number } | null>(null)

  const handleRunLint = useCallback(async () => {
    if (!project?.id || running) return
    setRunning(true)
    setResults([])
    try {
      const data = await lintApi.run(project.id)
      setResults(data.issues)
      setHasRun(true)
      if (data.issues.length === 0) {
        toast.success("All clear — no issues found!")
      }
    } catch (err) {
      console.error("Lint failed:", err)
      toast.error("Failed to run lint")
    } finally {
      setRunning(false)
    }
  }, [project, running])

  function handleOpenPage(issue: LintIssue) {
    const page = wikiPages.find((p) => p.path === issue.page)
    if (page) {
      setSelectedPageId(page.id)
      setActiveView("wiki")
    }
  }

  function handleFix(issue: LintIssue, index: number) {
    const id = `${issue.type}-${index}`
    setFixingId(id)
    const page = wikiPages.find((p) => p.path === issue.page)

    useReviewStore.getState().addItem({
      type: "confirm",
      title: `Fix: ${issue.page}`,
      description: issue.message,
      affectedPages: [issue.page],
      options: [
        { label: "Open & Edit", action: page ? `open:${page.title}` : "Skip" },
        { label: "Skip", action: "Skip" },
      ],
    })
    setResults((prev) => prev.filter((_, i) => i !== index))
    bumpDataVersion()
    setFixingId(null)
  }

  async function handleConfirmDeleteOrphan() {
    if (!project?.id || !orphanToDelete) return
    const { issue, index } = orphanToDelete
    const page = wikiPages.find((p) => p.path === issue.page)
    if (!page) {
      setOrphanToDelete(null)
      return
    }

    try {
      await pagesApi.delete(project.id, page.id)
      setResults((prev) => prev.filter((_, i) => i !== index))
      bumpDataVersion()
      toast.success(`Deleted "${page.title}"`)
    } catch (err) {
      console.error("Delete failed:", err)
      toast.error(`Failed to delete: ${err}`)
    } finally {
      setOrphanToDelete(null)
    }
  }

  const warnings = results.filter((r) => SEVERITY_MAP[r.type] === "warning")
  const infos = results.filter((r) => SEVERITY_MAP[r.type] !== "warning")

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Wiki Lint</h2>
          {hasRun && results.length > 0 && (
            <span className="rounded-full bg-destructive/20 px-2 py-0.5 text-xs font-medium text-destructive">
              {results.length} issue{results.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={handleRunLint}
            disabled={running || !project}
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${running ? "animate-spin" : ""}`} />
            {running ? "Running..." : "Run Lint"}
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {!hasRun ? (
          <div className="flex flex-col items-center justify-center gap-2 p-8 text-center text-sm text-muted-foreground">
            <CheckCircle2 className="h-8 w-8 text-muted-foreground/30" />
            <p>Run lint to check wiki health</p>
            <p className="text-xs">Checks for orphan pages, broken links, empty pages, and more</p>
          </div>
        ) : results.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 p-8 text-center text-sm text-muted-foreground">
            <CheckCircle2 className="h-8 w-8 text-primary/60" />
            <p className="text-primary font-medium">All clear!</p>
            <p className="text-xs">No issues found.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2 p-3">
            {warnings.length > 0 && (
              <SectionHeader icon={AlertTriangle} label="Warnings" count={warnings.length} color="text-destructive" />
            )}
            {warnings.map((issue, i) => (
              <LintCard
                key={`warn-${i}`}
                issue={issue}
                index={i}
                fixing={fixingId === `${issue.type}-${i}`}
                onOpenPage={handleOpenPage}
                onFix={handleFix}
                onDelete={issue.type === "orphan_page" ? (iss, idx) => setOrphanToDelete({ issue: iss, index: idx }) : undefined}
              />
            ))}
            {infos.length > 0 && (
              <SectionHeader icon={Info} label="Info" count={infos.length} color="text-primary" />
            )}
            {infos.map((issue, i) => {
              const realIndex = warnings.length + i
              return (
                <LintCard
                  key={`info-${i}`}
                  issue={issue}
                  index={realIndex}
                  fixing={fixingId === `${issue.type}-${realIndex}`}
                  onOpenPage={handleOpenPage}
                  onFix={handleFix}
                  onDelete={issue.type === "orphan_page" ? (iss, idx) => setOrphanToDelete({ issue: iss, index: idx }) : undefined}
                />
              )
            })}
          </div>
        )}
      </div>

      <AlertDialog open={!!orphanToDelete} onOpenChange={(open) => !open && setOrphanToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete orphan page?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete "{orphanToDelete?.issue.page}". This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDeleteOrphan}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function SectionHeader({
  icon: Icon,
  label,
  count,
  color,
}: {
  icon: typeof AlertTriangle
  label: string
  count: number
  color: string
}) {
  return (
    <div className={`flex items-center gap-1.5 px-1 py-1 text-xs font-semibold ${color}`}>
      <Icon className="h-3.5 w-3.5" />
      {label} ({count})
    </div>
  )
}

function LintCard({
  issue,
  index,
  fixing,
  onOpenPage,
  onFix,
  onDelete,
}: {
  issue: LintIssue
  index: number
  fixing: boolean
  onOpenPage: (issue: LintIssue) => void
  onFix: (issue: LintIssue, index: number) => void
  onDelete?: (issue: LintIssue, index: number) => void
}) {
  const config = typeConfig[issue.type] ?? { icon: AlertTriangle, label: issue.type }
  const Icon = config.icon
  const severity = SEVERITY_MAP[issue.type] ?? "info"

  return (
    <div className="rounded-lg border p-3 text-sm">
      <div className="mb-1.5 flex items-start gap-2">
        <Icon
          className={`mt-0.5 h-4 w-4 shrink-0 ${
            severity === "warning" ? "text-destructive" : "text-primary"
          }`}
        />
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{issue.page}</div>
          <div className="text-[11px] text-muted-foreground">{config.label}</div>
        </div>
      </div>

      <p className="mb-2 text-xs text-muted-foreground">{issue.message}</p>

      <div className="flex items-center gap-1.5 mt-2">
        <Button
          variant="outline"
          size="sm"
          className="h-6 text-xs gap-1"
          onClick={() => onOpenPage(issue)}
        >
          Open
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-6 text-xs gap-1"
          disabled={fixing}
          onClick={() => onFix(issue, index)}
        >
          <Wrench className="h-3 w-3" />
          {fixing ? "Fixing..." : "Fix"}
        </Button>
        {onDelete && (
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-xs gap-1 text-destructive hover:text-destructive"
            onClick={() => onDelete(issue, index)}
          >
            <Trash2 className="h-3 w-3" />
            Delete
          </Button>
        )}
      </div>
    </div>
  )
}
