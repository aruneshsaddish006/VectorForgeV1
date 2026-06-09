import type { DemoWorkspace } from "./types"

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000"

export async function fetchDemoWorkspace(signal?: AbortSignal): Promise<DemoWorkspace> {
  const response = await fetch(`${API_BASE_URL}/api/demo-workspace`, {
    signal,
    headers: {
      Accept: "application/json",
    },
  })

  if (!response.ok) {
    throw new Error(`Mock backend returned ${response.status}`)
  }

  return response.json()
}

export type AuthResponse = {
  token: string
  user: {
    id: string
    email: string
    fullName: string
    avatarUrl?: string | null
  }
  workspace?: {
    id: string
    name: string
    plan: string
  } | null
}

export type SignupResponse = {
  status: string
  user: AuthResponse["user"]
}

export type Workspace = {
  id: string
  name: string
  plan: string
}

export type Project = {
  id: string
  workspaceId: string
  name: string
  description?: string | null
  status: string
  createdAt: string
}

export type ProjectAssets = {
  workspaceId: string
  project: Project
  dataset: import("./types").DatasetSchema
  training: import("./types").TrainingRun
  models: import("./types").LeaderboardRow[]
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    if (typeof payload.detail === "string") return payload.detail
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => {
          const field = Array.isArray(item.loc) ? item.loc.filter((part: unknown) => part !== "body").join(".") : ""
          return field ? `${field}: ${item.msg}` : item.msg
        })
        .filter(Boolean)
        .join("; ")
    }
  } catch {
    // Keep the fallback below when the response is not JSON.
  }

  return `Request failed with ${response.status}`
}

async function postAuth(path: string, body: Record<string, unknown>): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response))
  }

  return response.json()
}

async function postWithAuth<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const token = window.localStorage.getItem("forge_ai_token")
  if (!token) {
    throw new Error("You need to log in first.")
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response))
  }

  return response.json()
}

export function signupUser(payload: {
  fullName: string
  email: string
  company: string
  password: string
}): Promise<SignupResponse> {
  return postAuth("/api/auth/signup", {
    full_name: payload.fullName,
    email: payload.email,
    company: payload.company,
    password: payload.password,
  }) as Promise<SignupResponse>
}

export function loginUser(payload: {
  email: string
  password: string
}): Promise<AuthResponse> {
  return postAuth("/api/auth/login", payload)
}

export function continueWithGoogle(): Promise<AuthResponse> {
  return postAuth("/api/auth/google", {
    email: "demo.user@gmail.com",
    full_name: "Demo Google User",
    provider_user_id: "google-demo-user",
    company: "Google Workspace",
  })
}

export function persistAuthSession(auth: AuthResponse) {
  window.localStorage.setItem("forge_ai_token", auth.token)
  window.localStorage.setItem("forge_ai_user", JSON.stringify(auth.user))
  if (auth.workspace) {
    window.localStorage.setItem("forge_ai_workspace", JSON.stringify(auth.workspace))
  } else {
    window.localStorage.removeItem("forge_ai_workspace")
  }
}

export function clearAuthSession() {
  window.localStorage.removeItem("forge_ai_token")
  window.localStorage.removeItem("forge_ai_user")
  window.localStorage.removeItem("forge_ai_workspace")
}

export function createWorkspace(payload: { name: string }): Promise<Workspace> {
  return postWithAuth<Workspace>("/api/workspaces", payload)
}

export function fetchWorkspaces(): Promise<Workspace[]> {
  return getWithAuth<Workspace[]>("/api/workspaces")
}

export function createProject(payload: {
  name: string
  description?: string
  workspaceId?: string
}): Promise<Project> {
  return postWithAuth<Project>("/api/projects", payload)
}

export function fetchProjects(workspaceId: string): Promise<Project[]> {
  return getWithAuth<Project[]>(`/api/projects?workspaceId=${encodeURIComponent(workspaceId)}`)
}

export function fetchProjectAssets(workspaceId: string, projectId: string): Promise<ProjectAssets> {
  return getWithAuth<ProjectAssets>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/projects/${encodeURIComponent(projectId)}/assets`,
  )
}

export async function logoutUser(): Promise<void> {
  try {
    await postWithAuth<{ status: string }>("/api/auth/logout")
  } catch {
    // Local logout should still succeed if the server session is already gone
    // or the backend is temporarily unavailable.
  } finally {
    clearAuthSession()
  }
}

export function persistWorkspace(workspace: Workspace) {
  window.localStorage.setItem("forge_ai_workspace", JSON.stringify(workspace))
}

async function getWithAuth<T>(path: string): Promise<T> {
  const token = window.localStorage.getItem("forge_ai_token")
  if (!token) {
    throw new Error("You need to log in first.")
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response))
  }

  return response.json()
}
