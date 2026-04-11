import { api, getToken } from "./client";

const BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

export interface Conversation {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export const chat = {
  listConversations: (projectId: string) =>
    api<Conversation[]>(`/projects/${projectId}/conversations`),
  createConversation: (projectId: string, title: string = "New Conversation") =>
    api<Conversation>(`/projects/${projectId}/conversations`, { method: "POST", body: JSON.stringify({ title }) }),
  getMessages: (convId: string) =>
    api<Message[]>(`/conversations/${convId}/messages`),
  sendMessage: (convId: string, content: string) =>
    api<Message>(`/conversations/${convId}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  deleteConversation: (convId: string) =>
    api(`/conversations/${convId}`, { method: "DELETE" }),
};

export function streamChat(projectId: string, convId: string, onToken: (t: string) => void, onDone: () => void, onError: (e: string) => void): () => void {
  const token = getToken();
  const url = `${BASE_URL}/projects/${projectId}/stream/chat/${convId}?token=${token}`;
  const source = new EventSource(url);

  source.addEventListener("token", (e) => {
    const data = JSON.parse((e as MessageEvent).data);
    onToken(data.text);
  });
  source.addEventListener("done", () => {
    source.close();
    onDone();
  });
  source.addEventListener("error", (e) => {
    source.close();
    const evt = e as MessageEvent;
    if (evt.data) {
      try {
        const data = JSON.parse(evt.data);
        onError(data.message || "Stream error");
      } catch {
        onError("Stream error");
      }
    } else {
      onError("Connection failed");
    }
  });

  return () => source.close();
}
