import { useEffect, useState } from "react"
import { Plus, Clock, X, FolderOpen, Network, Sparkles, BookOpen } from "lucide-react"
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
import { projects as projectsApi } from "@/api/projects"
import type { WikiProject } from "@/types/wiki"
import { useTranslation } from "react-i18next"

interface WelcomeScreenProps {
  onCreateProject: () => void
  onSelectProject: (project: WikiProject) => void
}

export function WelcomeScreen({
  onCreateProject,
  onSelectProject,
}: WelcomeScreenProps) {
  const { t } = useTranslation()
  const [recentProjects, setRecentProjects] = useState<WikiProject[]>([])
  const [projectToDelete, setProjectToDelete] = useState<string | null>(null)

  useEffect(() => {
    projectsApi.list().then(setRecentProjects).catch(() => {})
  }, [])

  async function handleConfirmDelete() {
    if (!projectToDelete) return
    try {
      await projectsApi.delete(projectToDelete)
      const updated = await projectsApi.list()
      setRecentProjects(updated)
    } catch {
      // ignore
    } finally {
      setProjectToDelete(null)
    }
  }

  return (
    <div className="flex h-full flex-col items-center justify-center bg-background px-4">
      <div className="w-full max-w-2xl space-y-12">
        {/* Onboarding Hero Section */}
        <div className="flex flex-col items-center text-center">
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <BookOpen className="h-10 w-10" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-foreground">
            {t("app.title") || "Welcome to Agent Wiki"}
          </h1>
          <p className="mt-3 text-lg text-muted-foreground max-w-[500px]">
            {t("app.subtitle") || "Your AI-powered workspace for deep research, document analysis, and knowledge graphs."}
          </p>
          <div className="mt-8">
            <Button size="lg" onClick={onCreateProject} className="h-12 px-8 text-base">
              <Plus className="mr-2 h-5 w-5" />
              {t("welcome.newProject") || "Create New Project"}
            </Button>
          </div>
        </div>

        {/* Feature Steps (Empty State Education) */}
        {recentProjects.length === 0 && (
          <div className="grid gap-6 sm:grid-cols-3 pt-8 border-t border-border/50">
            <div className="flex flex-col items-center text-center space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <FolderOpen className="h-6 w-6" />
              </div>
              <h3 className="font-semibold text-foreground">1. Upload Documents</h3>
              <p className="text-sm text-muted-foreground">Import PDFs, Markdown, or link URLs to build your base.</p>
            </div>
            <div className="flex flex-col items-center text-center space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <Sparkles className="h-6 w-6" />
              </div>
              <h3 className="font-semibold text-foreground">2. Deep Research</h3>
              <p className="text-sm text-muted-foreground">Let AI analyze content, extract entities, and summarize data.</p>
            </div>
            <div className="flex flex-col items-center text-center space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <Network className="h-6 w-6" />
              </div>
              <h3 className="font-semibold text-foreground">3. Explore Graph</h3>
              <p className="text-sm text-muted-foreground">Visualize relationships and navigate your knowledge visually.</p>
            </div>
          </div>
        )}

        {/* Recent Projects */}
        {recentProjects.length > 0 && (
          <div className="mx-auto w-full max-w-md pt-8 border-t border-border/50">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
              <Clock className="h-4 w-4" />
              {t("welcome.recentProjects") || "Recent Projects"}
            </div>
            <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              {recentProjects.map((proj) => (
                <div
                  key={proj.id}
                  className="group flex w-full items-center justify-between border-b border-border p-2 last:border-b-0 transition-colors hover:bg-accent/50"
                >
                  <button
                    onClick={() => onSelectProject(proj)}
                    className="flex min-w-0 flex-1 flex-col items-start px-3 py-2 text-left"
                  >
                    <span className="truncate text-sm font-semibold text-foreground">{proj.name}</span>
                    <span className="truncate text-xs text-muted-foreground mt-0.5">
                      Updated {new Date(proj.updated_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                    </span>
                  </button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      setProjectToDelete(proj.id)
                    }}
                    className="mr-2 h-8 w-8 text-muted-foreground opacity-0 hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                  >
                    <X className="h-4 w-4" />
                    <span className="sr-only">Delete project</span>
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!projectToDelete} onOpenChange={(open) => !open && setProjectToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete your
              project and remove all associated data from the server.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
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
