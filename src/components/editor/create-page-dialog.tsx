import { useState } from "react"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { pages as pagesApi } from "@/api/pages"
import { useWikiStore } from "@/stores/wiki-store"
import { toast } from "sonner"

const PAGE_TYPES = [
  { value: "entity", label: "Entity" },
  { value: "concept", label: "Concept" },
  { value: "query", label: "Query" },
  { value: "synthesis", label: "Synthesis" },
  { value: "comparison", label: "Comparison" },
  { value: "overview", label: "Overview" },
]

interface CreatePageDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CreatePageDialog({ open, onOpenChange }: CreatePageDialogProps) {
  const project = useWikiStore((s) => s.project)
  const bumpDataVersion = useWikiStore((s) => s.bumpDataVersion)
  const setSelectedPageId = useWikiStore((s) => s.setSelectedPageId)
  const setActiveView = useWikiStore((s) => s.setActiveView)

  const [title, setTitle] = useState("")
  const [type, setType] = useState("entity")
  const [error, setError] = useState("")
  const [creating, setCreating] = useState(false)

  async function handleCreate() {
    if (!title.trim()) {
      setError("Title is required")
      return
    }
    if (!project?.id) return

    setCreating(true)
    setError("")
    try {
      const slug = title
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .trim()
        .replace(/\s+/g, "-")
        .slice(0, 50)
      const dirMap: Record<string, string> = {
        entity: "entities",
        concept: "concepts",
        query: "queries",
        synthesis: "synthesis",
        comparison: "comparisons",
        overview: "overview",
      }
      const dir = dirMap[type] || "pages"
      const path = `wiki/${dir}/${slug}.md`

      const page = await pagesApi.create(project.id, {
        path,
        type,
        title: title.trim(),
        content: `# ${title.trim()}\n\n`,
        frontmatter: { created: new Date().toISOString().slice(0, 10), tags: [] },
      })

      bumpDataVersion()
      setSelectedPageId(page.id)
      setActiveView("wiki")
      toast.success(`Created "${title.trim()}"`)
      onOpenChange(false)
      setTitle("")
      setType("entity")
    } catch (err) {
      setError(String(err))
    } finally {
      setCreating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create New Page</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="page-title">Title</Label>
            <Input
              id="page-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Page title..."
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Type</Label>
            <div className="flex flex-wrap gap-2">
              {PAGE_TYPES.map((pt) => (
                <button
                  key={pt.value}
                  onClick={() => setType(pt.value)}
                  className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                    type === pt.value
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border hover:bg-accent"
                  }`}
                >
                  {pt.label}
                </button>
              ))}
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? "Creating..." : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
