import type { ConversationMessage, ConversationSession, DemoWorkspace, InterruptOption, InterruptPayload } from "./types"

// Main backend: auth, workspaces, projects (port 8000)
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000"

// Conversational service: independent deployment (port 8001)
export const CONV_API_BASE_URL =
  process.env.NEXT_PUBLIC_CONV_API_URL?.replace(/\/$/, "") || "http://localhost:8001"

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

export type DatasetRecord = {
  id: string
  workspaceId: string
  projectId: string
  projectName: string
  useCaseId?: string | null
  name: string
  sourceType: string
  storageUri?: string | null
  s3Path?: string | null
  dataFormat?: "csv" | "pdf" | null
  dataCategory?: "structured" | "unstructured" | null
  rowCount: number
  columnCount: number
  qualityScore?: number | null
  targetColumn?: string | null
  taskType?: string | null
  status: string
  createdAt: string
  updatedAt: string
}

export type ModelRecord = {
  trainingRunId: string
  workspaceId: string
  projectId: string
  projectName: string
  useCaseId: string
  useCaseName: string
  useCaseTaskType: string
  datasetId: string
  datasetName: string
  datasetS3Path?: string | null
  datasetFormat?: string | null
  datasetCategory?: string | null
  engine: string
  predictorType: string
  trainingStatus: string
  bestMetricName?: string | null
  bestMetricValue?: number | null
  computeCost?: number | null
  trainTimeSeconds?: number | null
  sagemakerJobArn?: string | null
  modelArtifactS3Path?: string | null
  errorMessage?: string | null
  leaderboardEntryId?: string | null
  rank?: number | null
  modelName?: string | null
  metricValue?: number | null
  inferenceLatencyMs?: number | null
  artifactS3Path?: string | null
  isBest: boolean
  metadata: Record<string, unknown>
  createdAt: string
  startedAt?: string | null
  completedAt?: string | null
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

async function postAuth<T = AuthResponse>(path: string, body: Record<string, unknown>): Promise<T> {
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
  return postAuth<SignupResponse>("/api/auth/signup", {
    full_name: payload.fullName,
    email: payload.email,
    company: payload.company,
    password: payload.password,
  })
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

export function fetchDatasets(workspaceId: string, projectId?: string): Promise<DatasetRecord[]> {
  const params = new URLSearchParams({ workspaceId })
  if (projectId) params.set("projectId", projectId)
  return getWithAuth<DatasetRecord[]>(`/api/datasets?${params.toString()}`)
}

export function fetchModels(workspaceId: string, projectId?: string): Promise<ModelRecord[]> {
  const params = new URLSearchParams({ workspaceId })
  if (projectId) params.set("projectId", projectId)
  return getWithAuth<ModelRecord[]>(`/api/models?${params.toString()}`)
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

// ---------------------------------------------------------------------------
// Conversational API client
// ---------------------------------------------------------------------------

/** Generate a UUID session_id on the frontend to correlate across services. */
export function generateSessionId(): string {
  return crypto.randomUUID()
}

/** Normalise snake_case API response message into camelCase ConversationMessage. */
function normaliseMessage(m: Record<string, unknown>): ConversationMessage {
  return {
    role: m.role as "user" | "agent",
    agentName: (m.agent_name ?? null) as string | null,
    content: m.content as string,
    timestamp: m.timestamp as string,
    cardType: (m.card_type ?? null) as string | null,
    cardData: (m.card_data ?? null) as Record<string, unknown> | null,
  }
}

/** Normalise snake_case interrupt payload into InterruptPayload. */
function normaliseInterrupt(raw: unknown): InterruptPayload | null {
  if (!raw || typeof raw !== "object") return null
  const r = raw as Record<string, unknown>
  return {
    type: r.type as InterruptPayload["type"],
    message: (r.message ?? "") as string,
    data: (r.data ?? null) as Record<string, unknown> | null,
    options: Array.isArray(r.options)
      ? (r.options as string[]).map((o) => (typeof o === "string" ? { value: o, label: o } : (o as InterruptOption)))
      : null,
    estimatedCostUsd: (r.estimated_cost_usd ?? null) as number | null,
    questions: (r.questions ?? null) as string[] | null,
    finalOutput: (r.final_output ?? null) as Record<string, unknown> | null,
    problemId: (r.problem_id ?? null) as string | null,
    problemName: (r.problem_name ?? null) as string | null,
    engine: (r.engine ?? null) as string | null,
  }
}

function normaliseSession(data: Record<string, unknown>): ConversationSession {
  const rawMessages = Array.isArray(data.messages) ? data.messages : []
  return {
    sessionId: data.session_id as string,
    status: data.status as string,
    messages: rawMessages.map((m) => normaliseMessage(m as Record<string, unknown>)),
    interrupt: normaliseInterrupt(data.interrupt),
    finalOutput: (data.final_output ?? null) as Record<string, unknown> | null,
  }
}

async function convFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${CONV_API_BASE_URL}${path}`, {
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    ...init,
  })
  if (!response.ok) throw new Error(await parseApiError(response))
  return response
}

/** Start a new conversation. Session ID generated by the caller via generateSessionId(). */
export async function startConversation(sessionId: string, message: string): Promise<ConversationSession> {
  const res = await convFetch("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  const json = await res.json()
  return normaliseSession(json.data)
}

/** Resume the graph after an interrupt with the user's response payload. */
export async function respondToInterrupt(
  sessionId: string,
  payload: Record<string, unknown>,
): Promise<ConversationSession> {
  const res = await convFetch(`/api/v1/conversations/${sessionId}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const json = await res.json()
  return normaliseSession(json.data)
}

/** Upload a dataset file for a sub-problem and resume the paused graph. */
export async function uploadDataset(sessionId: string, probId: string, file: File): Promise<void> {
  const form = new FormData()
  form.append("problem_id", probId)
  form.append("file", file)
  await convFetch(`/api/v1/conversations/${sessionId}/upload-dataset`, {
    method: "POST",
    body: form,
  })
}

/** Poll current conversation state — used after upload or to hydrate on refresh. */
export async function getConversationState(sessionId: string): Promise<ConversationSession> {
  const res = await convFetch(`/api/v1/conversations/${sessionId}`)
  const json = await res.json()
  return normaliseSession(json.data)
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
