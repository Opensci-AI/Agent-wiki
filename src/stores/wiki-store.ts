import { create } from "zustand"
import type { WikiProject } from "@/types/wiki"
import type { WikiPage } from "@/api/pages"

// Active task tracking (persists across tab switches)
export interface ActiveTask {
  sourceId: string
  taskId: string
  type: "extract" | "ingest"
  status: string
  statusDetail: string | null
  progress: number
}

interface WikiState {
  project: WikiProject | null
  pages: WikiPage[]
  selectedPageId: string | null
  selectedPage: WikiPage | null
  chatExpanded: boolean
  activeView: "wiki" | "sources" | "search" | "graph" | "lint" | "review" | "settings"
  dataVersion: number
  user: { id: string; email: string; display_name: string; is_admin: boolean } | null
  activeTasks: Map<string, ActiveTask>  // sourceId -> task

  setProject: (project: WikiProject | null) => void
  setPages: (pages: WikiPage[]) => void
  setSelectedPageId: (id: string | null) => void
  setSelectedPage: (page: WikiPage | null) => void
  setChatExpanded: (expanded: boolean) => void
  setActiveView: (view: WikiState["activeView"]) => void
  setUser: (user: WikiState["user"]) => void
  bumpDataVersion: () => void
  setActiveTask: (sourceId: string, task: ActiveTask | null) => void
  updateActiveTask: (sourceId: string, update: Partial<ActiveTask>) => void
}

export const useWikiStore = create<WikiState>((set) => ({
  project: null,
  pages: [],
  selectedPageId: null,
  selectedPage: null,
  chatExpanded: false,
  activeView: "wiki",
  dataVersion: 0,
  user: null,
  activeTasks: new Map(),

  setProject: (project) => set({ project }),
  setPages: (pages) => set({ pages }),
  setSelectedPageId: (selectedPageId) => set({ selectedPageId }),
  setSelectedPage: (selectedPage) => set({ selectedPage }),
  setChatExpanded: (chatExpanded) => set({ chatExpanded }),
  setActiveView: (activeView) => set({ activeView }),
  setUser: (user) => set({ user }),
  bumpDataVersion: () => set((state) => ({ dataVersion: state.dataVersion + 1 })),
  setActiveTask: (sourceId, task) => set((state) => {
    const newTasks = new Map(state.activeTasks)
    if (task) {
      newTasks.set(sourceId, task)
    } else {
      newTasks.delete(sourceId)
    }
    return { activeTasks: newTasks }
  }),
  updateActiveTask: (sourceId, update) => set((state) => {
    const existing = state.activeTasks.get(sourceId)
    if (!existing) return state
    const newTasks = new Map(state.activeTasks)
    newTasks.set(sourceId, { ...existing, ...update })
    return { activeTasks: newTasks }
  }),
}))

export type { WikiState }
