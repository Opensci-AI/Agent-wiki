import { useState } from "react"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { sources as sourcesApi } from "@/api/sources"
import { toast } from "sonner"

interface WebClipDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  onClipped: () => void
}

export function WebClipDialog({ open, onOpenChange, projectId, onClipped }: WebClipDialogProps) {
  const [url, setUrl] = useState("")
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [error, setError] = useState("")
  const [clipping, setClipping] = useState(false)

  async function handleClip() {
    if (!url.trim()) {
      setError("URL is required")
      return
    }
    if (!title.trim()) {
      setError("Title is required")
      return
    }

    setClipping(true)
    setError("")
    try {
      await sourcesApi.clip(projectId, {
        title: title.trim(),
        url: url.trim(),
        content: content.trim(),
      })
      toast.success(`Clipped "${title.trim()}"`)
      onClipped()
      onOpenChange(false)
      setUrl("")
      setTitle("")
      setContent("")
    } catch (err) {
      setError(String(err))
    } finally {
      setClipping(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Web Clip</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="clip-url">URL</Label>
            <Input
              id="clip-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="clip-title">Title</Label>
            <Input
              id="clip-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Article title"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="clip-content">Content (optional)</Label>
            <textarea
              id="clip-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Paste content or leave empty to auto-extract..."
              rows={4}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleClip} disabled={clipping}>
            {clipping ? "Clipping..." : "Clip"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
