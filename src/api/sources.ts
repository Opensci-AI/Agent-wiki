import { api, getToken } from "./client";

export interface Source {
  id: string;
  project_id: string;
  filename: string;
  original_name: string;
  content_type: string;
  file_size: number;
  status: string;
  extracted_text: string | null;
  created_at: string;
}

export const sources = {
  list: (projectId: string) => api<Source[]>(`/projects/${projectId}/sources`),
  get: (projectId: string, sourceId: string) => api<Source>(`/projects/${projectId}/sources/${sourceId}`),
  upload: async (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api<Source>(`/projects/${projectId}/sources/upload`, { method: "POST", body: formData });
  },
  clip: (projectId: string, data: { title: string; url: string; content: string }) =>
    api<Source>(`/projects/${projectId}/sources/clip`, { method: "POST", body: JSON.stringify(data) }),
  delete: (projectId: string, sourceId: string) =>
    api(`/projects/${projectId}/sources/${sourceId}`, { method: "DELETE" }),
  extract: (projectId: string, sourceId: string) =>
    api(`/projects/${projectId}/sources/${sourceId}/extract`, { method: "POST" }),
  /** Build a URL that can be used as `src` in <img>/<video>/<audio> tags. */
  fileUrl: (projectId: string, sourceId: string): string => {
    const base = import.meta.env.VITE_API_URL || "/api/v1";
    const token = getToken();
    return `${base}/projects/${projectId}/sources/${sourceId}/file${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  },
};
