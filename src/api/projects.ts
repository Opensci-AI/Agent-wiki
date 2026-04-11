import { api } from "./client";

export interface Project {
  id: string;
  name: string;
  purpose: string;
  schema_text: string;
  created_at: string;
  updated_at: string;
}

export const projects = {
  list: () => api<Project[]>("/projects"),
  get: (id: string) => api<Project>(`/projects/${id}`),
  create: (name: string) => api<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
  update: (id: string, data: Partial<Project>) => api<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) => api(`/projects/${id}`, { method: "DELETE" }),
};
