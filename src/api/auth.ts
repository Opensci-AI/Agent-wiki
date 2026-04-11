import { api, setToken } from "./client";

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
  oauth_provider: string | null;
  created_at: string;
}

export async function register(email: string, password: string, displayName: string) {
  const data = await api<{ access_token: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  setToken(data.access_token);
  return data;
}

export async function login(email: string, password: string) {
  const data = await api<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data;
}

export async function getMe() {
  return api<User>("/auth/me");
}

export async function logout() {
  setToken(null);
  window.location.href = "/login";
}
