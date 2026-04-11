import { Routes, Route, Navigate } from "react-router-dom"
import { ChatPanel } from "@/components/chat/chat-panel"
import { SettingsView } from "@/components/settings/settings-view"
import { SourcesView } from "@/components/sources/sources-view"
import { ReviewView } from "@/components/review/review-view"
import { LintView } from "@/components/lint/lint-view"
import { SearchView } from "@/components/search/search-view"
import { GraphView } from "@/components/graph/graph-view"

export function ContentArea() {
  return (
    <Routes>
      <Route path="chat" element={<ChatPanel />} />
      <Route path="chat/:conversationId" element={<ChatPanel />} />
      <Route path="sources" element={<SourcesView />} />
      <Route path="graph" element={<GraphView />} />
      <Route path="search" element={<SearchView />} />
      <Route path="review" element={<ReviewView />} />
      <Route path="lint" element={<LintView />} />
      <Route path="settings" element={<SettingsView />} />
      {/* Default to chat */}
      <Route path="*" element={<Navigate to="chat" replace />} />
    </Routes>
  )
}
