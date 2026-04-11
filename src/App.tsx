import { useEffect, useState } from "react"
import { Routes, Route, Navigate, useNavigate, useParams } from "react-router-dom"
import i18n from "@/i18n"
import { useWikiStore } from "@/stores/wiki-store"
import { useChatStore } from "@/stores/chat-store"
import { getMe, getToken } from "@/api"
import { projects as projectsApi } from "@/api/projects"
import { pages as pagesApi } from "@/api/pages"
import { config as configApi } from "@/api/config"
import { chat as chatApi } from "@/api/chat"
import { AppLayout } from "@/components/layout/app-layout"
import { WelcomeScreen } from "@/components/project/welcome-screen"
import { CreateProjectDialog } from "@/components/project/create-project-dialog"
import LoginPage from "@/pages/login"
import RegisterPage from "@/pages/register"
import type { WikiProject } from "@/types/wiki"

// Auth guard wrapper
function RequireAuth({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const setUser = useWikiStore((s) => s.setUser)
  const [loading, setLoading] = useState(true)
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    async function checkAuth() {
      try {
        const token = getToken()
        if (!token) {
          navigate("/login", { replace: true })
          return
        }
        const user = await getMe()
        setUser(user)

        // Load config (language)
        try {
          const cfg = await configApi.get()
          if (cfg.language) {
            await i18n.changeLanguage(cfg.language)
          }
        } catch {
          // ignore
        }

        setAuthed(true)
      } catch {
        navigate("/login", { replace: true })
      } finally {
        setLoading(false)
      }
    }
    checkAuth()
  }, [])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-muted-foreground">
        Loading...
      </div>
    )
  }

  return authed ? <>{children}</> : null
}

// Project selection screen
function ProjectsPage() {
  const navigate = useNavigate()
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  async function handleProjectOpened(proj: WikiProject) {
    navigate(`/projects/${proj.id}`)
  }

  return (
    <>
      <WelcomeScreen
        onCreateProject={() => setShowCreateDialog(true)}
        onSelectProject={handleProjectOpened}
      />
      <CreateProjectDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onCreated={handleProjectOpened}
      />
    </>
  )
}

// Project layout - loads project data and renders AppLayout
function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const project = useWikiStore((s) => s.project)
  const setProject = useWikiStore((s) => s.setProject)
  const setPages = useWikiStore((s) => s.setPages)
  const [loading, setLoading] = useState(true)
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  useEffect(() => {
    async function loadProject() {
      if (!projectId) {
        navigate("/projects", { replace: true })
        return
      }

      try {
        const proj = await projectsApi.get(projectId)
        setProject(proj)

        // Load pages
        const pageList = await pagesApi.list(proj.id)
        setPages(pageList)

        // Load conversations
        try {
          const convs = await chatApi.listConversations(proj.id)
          useChatStore.setState({
            conversations: convs.map((c) => ({
              id: c.id,
              title: c.title,
              createdAt: new Date(c.created_at).getTime(),
              updatedAt: new Date(c.updated_at).getTime(),
            })),
          })
        } catch {
          // ignore
        }
      } catch {
        navigate("/projects", { replace: true })
      } finally {
        setLoading(false)
      }
    }
    loadProject()
  }, [projectId])

  function handleSwitchProject() {
    setProject(null)
    setPages([])
    useChatStore.setState({ conversations: [], activeConversationId: null, messages: [] })
    navigate("/projects")
  }

  async function handleProjectCreated(proj: WikiProject) {
    navigate(`/projects/${proj.id}`)
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-muted-foreground">
        Loading project...
      </div>
    )
  }

  if (!project) {
    return null
  }

  return (
    <>
      <AppLayout onSwitchProject={handleSwitchProject} />
      <CreateProjectDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onCreated={handleProjectCreated}
      />
    </>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected routes */}
      <Route
        path="/projects"
        element={
          <RequireAuth>
            <ProjectsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/projects/:projectId/*"
        element={
          <RequireAuth>
            <ProjectLayout />
          </RequireAuth>
        }
      />

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  )
}

export default App
