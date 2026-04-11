import { api } from "./client";

export interface TaskStatus {
  id: string;
  type: string;
  status: string;
  status_detail: string | null;  // Human-readable: "Extracting text from PDF..."
  current_step: string | null;   // Machine-readable: "extract_text"
  progress_pct: number;
  error: string | null;
  result: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export const ingest = {
  start: (projectId: string, sourceId: string) =>
    api<TaskStatus>(`/projects/${projectId}/ingest`, { method: "POST", body: JSON.stringify({ source_id: sourceId }) }),
  status: (projectId: string, taskId: string) =>
    api<TaskStatus>(`/projects/${projectId}/ingest/${taskId}`),
  cancel: (projectId: string, taskId: string) =>
    api(`/projects/${projectId}/ingest/${taskId}/cancel`, { method: "POST" }),
};

// Generic task status (works for extraction, ingest, etc.)
export const tasks = {
  status: (projectId: string, taskId: string) =>
    api<TaskStatus>(`/projects/${projectId}/tasks/${taskId}`),
};
