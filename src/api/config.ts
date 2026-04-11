import { api } from "./client";

export interface AppConfig {
  llm_config?: Record<string, any>;
  search_config?: Record<string, any>;
  language?: string;
}

export const config = {
  get: () => api<AppConfig>("/config"),
  update: (data: AppConfig) => api<AppConfig>("/config", { method: "PUT", body: JSON.stringify(data) }),
  getAdmin: () => api<AppConfig>("/admin/config"),
  updateAdmin: (data: AppConfig) => api<AppConfig>("/admin/config", { method: "PUT", body: JSON.stringify(data) }),
};
