import { api } from "./client";

export interface WikiPage {
  id: string;
  project_id: string;
  path: string;
  type: string;
  title: string;
  content: string;
  frontmatter: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export const pages = {
  list: (projectId: string, type?: string) =>
    api<WikiPage[]>(`/projects/${projectId}/pages${type ? `?type=${type}` : ""}`),
  get: (projectId: string, pageId: string) =>
    api<WikiPage>(`/projects/${projectId}/pages/${pageId}`),
  getByPath: (projectId: string, path: string) =>
    api<WikiPage>(`/projects/${projectId}/pages/by-path?path=${encodeURIComponent(path)}`),
  create: (projectId: string, data: { path: string; type: string; title: string; content?: string; frontmatter?: Record<string, any> }) =>
    api<WikiPage>(`/projects/${projectId}/pages`, { method: "POST", body: JSON.stringify(data) }),
  update: (projectId: string, pageId: string, data: { title?: string; content?: string; frontmatter?: Record<string, any> }) =>
    api<WikiPage>(`/projects/${projectId}/pages/${pageId}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (projectId: string, pageId: string) =>
    api(`/projects/${projectId}/pages/${pageId}`, { method: "DELETE" }),
  related: (projectId: string, source: string) =>
    api<WikiPage[]>(`/projects/${projectId}/pages/related?source=${encodeURIComponent(source)}`),
  search: (projectId: string, query: string) =>
    api<WikiPage[]>(`/projects/${projectId}/search?q=${encodeURIComponent(query)}`),
};

export interface LintIssue {
  type: string
  page: string
  message: string
}

export const lint = {
  run: (projectId: string) =>
    api<{ issues: LintIssue[] }>(`/projects/${projectId}/lint`),
};

export interface GraphNode {
  id: string
  title: string
  path: string
  type: string
}

export interface GraphEdge {
  source: string
  target: string
  label: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphInsightItem {
  id: string
  title: string
  path: string
  incoming_links?: number
}

export interface GraphInsights {
  orphans: GraphInsightItem[]
  hubs: GraphInsightItem[]
}

export const graph = {
  build: (projectId: string) =>
    api<GraphData>(`/projects/${projectId}/graph`),
  insights: (projectId: string) =>
    api<GraphInsights>(`/projects/${projectId}/graph/insights`),
};
