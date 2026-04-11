import { useNavigate, useLocation } from "react-router-dom"
import {
  MessageSquare, FolderOpen, Search, Network, ClipboardCheck, Settings, ArrowLeftRight, ClipboardList, Globe,
} from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { useWikiStore } from "@/stores/wiki-store"
import { useReviewStore } from "@/stores/review-store"
import { useResearchStore } from "@/stores/research-store"
import { useTranslation } from "react-i18next"
import logoImg from "@/assets/logo.jpg"

type NavRoute = "chat" | "sources" | "search" | "graph" | "lint" | "review" | "settings"

const NAV_ITEMS: { route: NavRoute; icon: typeof MessageSquare; labelKey: string }[] = [
  { route: "chat", icon: MessageSquare, labelKey: "nav.wiki" },
  { route: "sources", icon: FolderOpen, labelKey: "nav.sources" },
  { route: "search", icon: Search, labelKey: "nav.search" },
  { route: "graph", icon: Network, labelKey: "nav.graph" },
  { route: "lint", icon: ClipboardCheck, labelKey: "nav.lint" },
  { route: "review", icon: ClipboardList, labelKey: "nav.review" },
]

interface IconSidebarProps {
  onSwitchProject: () => void
}

export function IconSidebar({ onSwitchProject }: IconSidebarProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const project = useWikiStore((s) => s.project)
  const pendingCount = useReviewStore((s) => s.items.filter((i) => !i.resolved).length)
  const researchPanelOpen = useResearchStore((s) => s.panelOpen)
  const researchActiveCount = useResearchStore((s) => s.tasks.filter((t) => t.status !== "done" && t.status !== "error").length)
  const toggleResearchPanel = useResearchStore((s) => s.setPanelOpen)

  // Determine active route from URL
  const pathParts = location.pathname.split("/")
  const activeRoute = pathParts[3] || "chat" // /projects/:id/:route

  function handleNavigate(route: NavRoute) {
    if (project) {
      navigate(`/projects/${project.id}/${route}`)
    }
  }

  return (
    <TooltipProvider>
      <div className="flex h-full w-12 flex-col items-center border-r bg-muted/50 py-2">
        {/* Logo */}
        <div className="mb-2 flex items-center justify-center">
          <img
            src={logoImg}
            alt="LLM Wiki"
            className="h-8 w-8 rounded-[22%]"
          />
        </div>
        {/* Top: main nav items + Deep Research */}
        <div className="flex flex-1 flex-col items-center gap-1">
          {NAV_ITEMS.map(({ route, icon: Icon, labelKey }) => (
            <Tooltip key={route}>
              <TooltipTrigger
                onClick={() => handleNavigate(route)}
                className={`relative flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
                  activeRoute === route
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
                }`}
              >
                <Icon className="h-5 w-5" />
                {route === "review" && pendingCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
                    {pendingCount > 99 ? "99+" : pendingCount}
                  </span>
                )}
              </TooltipTrigger>
              <TooltipContent side="right">
                {t(labelKey)}
                {route === "review" && pendingCount > 0 && ` (${pendingCount})`}
              </TooltipContent>
            </Tooltip>
          ))}
          {/* Deep Research — same row as other nav items */}
          <Tooltip>
            <TooltipTrigger
              onClick={() => toggleResearchPanel(!researchPanelOpen)}
              className={`relative flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
                researchPanelOpen
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
              }`}
            >
              <Globe className="h-5 w-5" />
              {researchActiveCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
                  {researchActiveCount}
                </span>
              )}
            </TooltipTrigger>
            <TooltipContent side="right">Deep Research</TooltipContent>
          </Tooltip>
        </div>
        {/* Bottom: settings + switch project */}
        <div className="flex flex-col items-center gap-1 pb-1">
          <Tooltip>
            <TooltipTrigger
              onClick={() => handleNavigate("settings")}
              className={`flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
                activeRoute === "settings"
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
              }`}
            >
              <Settings className="h-5 w-5" />
            </TooltipTrigger>
            <TooltipContent side="right">{t("nav.settings")}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger
              onClick={onSwitchProject}
              className="flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent/50 hover:text-accent-foreground"
            >
              <ArrowLeftRight className="h-5 w-5" />
            </TooltipTrigger>
            <TooltipContent side="right">{t("nav.switchProject")}</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  )
}
