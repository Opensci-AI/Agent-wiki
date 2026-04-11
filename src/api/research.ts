import { api } from "./client";
import type { TaskStatus } from "./ingest";

export const research = {
  start: (projectId: string, topic: string, searchQueries: string[] = []) =>
    api<TaskStatus>(`/projects/${projectId}/research`, { method: "POST", body: JSON.stringify({ topic, search_queries: searchQueries }) }),
  status: (projectId: string, taskId: string) =>
    api<TaskStatus>(`/projects/${projectId}/research/${taskId}`),
};
