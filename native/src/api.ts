import * as SecureStore from "expo-secure-store";

import type { User } from "./types";

const API_BASE = process.env.EXPO_PUBLIC_API_BASE ?? "https://api.narutoooo.com";
const TOKEN_KEY = "nihongo-native-token";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "网络请求失败");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function authenticate(
  mode: "login" | "register",
  username: string,
  password: string,
): Promise<User> {
  const session = await api<{ access_token: string; user: User }>(`/api/auth/native/${mode}`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  await SecureStore.setItemAsync(TOKEN_KEY, session.access_token);
  return session.user;
}

export async function restoreSession(): Promise<User | null> {
  if (!(await SecureStore.getItemAsync(TOKEN_KEY))) return null;
  try {
    return await api<User>("/api/auth/me");
  } catch {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    return null;
  }
}

export async function clearSession(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}
