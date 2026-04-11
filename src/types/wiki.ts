export interface WikiProject {
  id: string
  name: string
  purpose: string
  schema_text: string
  created_at: string
  updated_at: string
}

export interface WikiPage {
  id: string
  project_id: string
  path: string
  type: string
  title: string
  content: string
  frontmatter: Record<string, unknown>
  created_at: string
  updated_at: string
}

// Keep FileNode for backward compatibility with tree components
export interface FileNode {
  name: string
  path: string
  is_dir: boolean
  children?: FileNode[]
}
