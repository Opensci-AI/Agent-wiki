import { KnowledgeTree } from "./knowledge-tree"

export function SidebarPanel() {

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 border-b">
        <div className="flex-1 px-3 py-1.5 text-xs font-medium text-foreground border-b-2 border-primary">
          Knowledge
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <KnowledgeTree />
      </div>
    </div>
  )
}
