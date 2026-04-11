import { useCallback } from "react"
import {
  AlertTriangle,
  Copy,
  FileQuestion,
  CheckCircle2,
  Lightbulb,
  MessageSquare,
  X,
  Check,
  Trash2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { useReviewStore, type ReviewItem } from "@/stores/review-store"
import { useWikiStore } from "@/stores/wiki-store"
import { pages as pagesApi } from "@/api/pages"
import { research } from "@/api/research"

const typeConfig: Record<ReviewItem["type"], { icon: typeof AlertTriangle; label: string; color: string }> = {
  contradiction: { icon: AlertTriangle, label: "Contradiction", color: "text-destructive" },
  duplicate: { icon: Copy, label: "Possible Duplicate", color: "text-primary" },
  "missing-page": { icon: FileQuestion, label: "Missing Page", color: "text-primary" },
  confirm: { icon: MessageSquare, label: "Needs Confirmation", color: "text-foreground" },
  suggestion: { icon: Lightbulb, label: "Suggestion", color: "text-primary" },
}

export function ReviewView() {
  const items = useReviewStore((s) => s.items)
  const resolveItem = useReviewStore((s) => s.resolveItem)
  const dismissItem = useReviewStore((s) => s.dismissItem)
  const clearResolved = useReviewStore((s) => s.clearResolved)
  const project = useWikiStore((s) => s.project)
  const bumpDataVersion = useWikiStore((s) => s.bumpDataVersion)

  const handleResolve = useCallback(async (id: string, action: string) => {
    const projectId = project?.id
    if (!projectId) {
      resolveItem(id, action)
      return
    }

    // Deep Research
    if (action === "__deep_research__") {
      const item = items.find((i) => i.id === id)
      if (item) {
        const topic = item.title.replace(/^(Save to Wiki|Create|Research)[:\s]*/i, "").trim() || item.description.split("\n")[0]
        research.start(projectId, topic, item.searchQueries).catch((err) =>
          console.error("Failed to start research:", err)
        )
        resolveItem(id, "Queued for research")
      } else {
        resolveItem(id, action)
      }
      return
    }

    if (action.startsWith("save:")) {
      try {
        const encoded = action.slice(5)
        const content = decodeURIComponent(atob(encoded))
        const cleanContent = content
          .replace(/<!--\s*save-worthy:.*?-->/g, "")
          .replace(/<!--\s*sources:.*?-->/g, "")
          .trimEnd()

        const firstLine = cleanContent.split("\n").find((l) => l.trim() && !l.startsWith("<!--"))?.replace(/^#+\s*/, "").trim() ?? "Saved Query"
        const title = firstLine.slice(0, 60)
        const slug = title.toLowerCase().replace(/[^a-z0-9\s-]/g, "").trim().replace(/\s+/g, "-").slice(0, 50)
        const date = new Date().toISOString().slice(0, 10)

        await pagesApi.create(projectId, {
          path: `wiki/queries/${slug}-${date}.md`,
          type: "query",
          title,
          content: cleanContent,
          frontmatter: { created: date, tags: [] },
        })

        bumpDataVersion()
        resolveItem(id, "Saved to Wiki")
      } catch (err) {
        console.error("Failed to save to wiki from review:", err)
        resolveItem(id, "Save failed")
      }
    } else if (action.startsWith("open:")) {
      const page = action.slice(5)
      // Try to find the page by searching the cached pages
      const wikiPages = useWikiStore.getState().pages
      const found = wikiPages.find(
        (p) => p.title === page || p.path.includes(page)
      )
      if (found) {
        useWikiStore.getState().setSelectedPageId(found.id)
        useWikiStore.getState().setActiveView("wiki")
      }
      resolveItem(id, action)
    } else if (action.startsWith("delete:")) {
      // Delete a page by finding it
      const pagePath = action.slice(7)
      const wikiPages = useWikiStore.getState().pages
      const found = wikiPages.find((p) => p.path === pagePath || p.path.includes(pagePath))
      if (found) {
        try {
          await pagesApi.delete(projectId, found.id)
          bumpDataVersion()
          resolveItem(id, "Deleted")
        } catch (err) {
          console.error("Failed to delete:", err)
          resolveItem(id, "Delete failed")
        }
      } else {
        resolveItem(id, "Page not found")
      }
    } else if (actionLooksLikeResearch(action)) {
      const item = items.find((i) => i.id === id)
      if (item) {
        const topic = action.replace(/^research\s*/i, "").trim() || item.description.split("\n")[0]
        research.start(projectId, topic).catch((err) =>
          console.error("Failed to start research:", err)
        )
        resolveItem(id, "Queued for deep research")
      } else {
        resolveItem(id, action)
      }
    } else if (actionLooksLikeCreate(action)) {
      const item = items.find((i) => i.id === id)
      if (item) {
        try {
          const title = item.title.replace(/^(Create|Save|Add)[:\s]*/i, "").trim() || "Untitled"
          const slug = title.toLowerCase().replace(/[^a-z0-9\s-]/g, "").trim().replace(/\s+/g, "-").slice(0, 50)
          const date = new Date().toISOString().slice(0, 10)
          const pageType = detectPageType(action, item.type)
          const dir = pageType === "query" ? "queries" : pageType === "entity" ? "entities" : pageType === "concept" ? "concepts" : "queries"

          await pagesApi.create(projectId, {
            path: `wiki/${dir}/${slug}-${date}.md`,
            type: pageType,
            title,
            content: `# ${title}\n\n${item.description}\n`,
            frontmatter: { created: date, tags: [], related: [] },
          })

          bumpDataVersion()
          resolveItem(id, `Created: wiki/${dir}/${slug}-${date}.md`)
        } catch (err) {
          console.error("Failed to create page from review:", err)
          resolveItem(id, "Create failed")
        }
      } else {
        resolveItem(id, action)
      }
    } else {
      resolveItem(id, action)
    }
  }, [project, items, resolveItem, bumpDataVersion])

  const pending = items.filter((i) => !i.resolved)
  const resolved = items.filter((i) => i.resolved)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold">
          Review
          {pending.length > 0 && (
            <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
              {pending.length}
            </span>
          )}
        </h2>
        {resolved.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearResolved} className="text-xs">
            <Trash2 className="mr-1 h-3 w-3" />
            Clear resolved
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 p-8 text-center text-sm text-muted-foreground">
            <CheckCircle2 className="h-8 w-8 text-muted-foreground/30" />
            <p>All clear -- nothing to review</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2 p-3">
            {pending.map((item) => (
              <ReviewCard
                key={item.id}
                item={item}
                onResolve={handleResolve}
                onDismiss={dismissItem}
              />
            ))}
            {resolved.length > 0 && pending.length > 0 && (
              <div className="my-2 text-center text-xs text-muted-foreground">
                -- Resolved --
              </div>
            )}
            {resolved.map((item) => (
              <ReviewCard
                key={item.id}
                item={item}
                onResolve={handleResolve}
                onDismiss={dismissItem}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ReviewCard({
  item,
  onResolve,
  onDismiss,
}: {
  item: ReviewItem
  onResolve: (id: string, action: string) => void
  onDismiss: (id: string) => void
}) {
  const config = typeConfig[item.type]
  const Icon = config.icon

  return (
    <div
      className={`rounded-lg border p-3 text-sm transition-opacity ${
        item.resolved ? "opacity-50" : ""
      }`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 shrink-0 ${config.color}`} />
          <span className="font-medium">{item.title}</span>
        </div>
        <button
          onClick={() => onDismiss(item.id)}
          className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-muted"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <p className="mb-3 text-xs text-muted-foreground">{item.description}</p>

      {item.affectedPages && item.affectedPages.length > 0 && (
        <div className="mb-3 text-xs text-muted-foreground">
          Pages: {item.affectedPages.join(", ")}
        </div>
      )}

      {!item.resolved ? (
        <div className="flex flex-wrap gap-1.5">
          {(item.type === "suggestion" || item.type === "missing-page") && (
            <Button
              variant="default"
              size="sm"
              className="h-7 text-xs gap-1"
              onClick={() => onResolve(item.id, "__deep_research__")}
            >
              Deep Research
            </Button>
          )}
          {item.options.map((opt) => (
            <Button
              key={opt.action}
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => onResolve(item.id, opt.action)}
            >
              {opt.label}
            </Button>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-1 text-xs text-primary">
          <Check className="h-3 w-3" />
          {item.resolvedAction}
        </div>
      )}
    </div>
  )
}

function actionLooksLikeResearch(action: string): boolean {
  if (action.startsWith("__")) return false
  const lower = action.toLowerCase()
  return (
    lower.includes("research") ||
    lower.includes("investigate") ||
    lower.includes("explore") ||
    lower.includes("look into")
  )
}

function actionIsDismissal(action: string): boolean {
  const lower = action.toLowerCase()
  return (
    lower === "skip" ||
    lower === "dismiss" ||
    lower === "ignore" ||
    lower === "approve" ||
    lower === "keep existing" ||
    lower === "no"
  )
}

function actionLooksLikeCreate(action: string): boolean {
  return !actionIsDismissal(action)
}

function detectPageType(action: string, reviewType: string): string {
  const lower = action.toLowerCase()
  if (lower.includes("entity")) return "entity"
  if (lower.includes("concept")) return "concept"
  if (lower.includes("comparison") || lower.includes("compare")) return "comparison"
  if (lower.includes("synthesis")) return "synthesis"
  if (reviewType === "missing-page") return "concept"
  if (reviewType === "contradiction") return "query"
  if (reviewType === "suggestion") return "query"
  return "query"
}
