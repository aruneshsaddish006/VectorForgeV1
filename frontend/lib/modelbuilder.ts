export const DEFAULT_MODEL_API_BASE_URL =
  process.env.NEXT_PUBLIC_MODEL_API_URL?.replace(/\/$/, "") || "http://localhost:8000"

export type ArtifactTargetScope = "runs" | "sessions"

export type ModelBuilderRequestOptions = {
  baseUrl: string
  method?: "GET" | "POST"
  body?: unknown
}

async function parseModelBuilderError(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === "string") return detail
    if (detail && typeof detail === "object") return JSON.stringify(detail, null, 2)
  } catch {
    try {
      const text = await response.text()
      if (text) return text
    } catch {
      // Keep the fallback below.
    }
  }

  return `Modelbuilder request failed with ${response.status}`
}

export function modelBuilderProxyUrl(path: string, baseUrl: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  return `/api/modelbuilder${normalizedPath}?baseUrl=${encodeURIComponent(baseUrl.replace(/\/$/, ""))}`
}

export async function modelBuilderRequest<T = unknown>(
  path: string,
  { baseUrl, method = "GET", body }: ModelBuilderRequestOptions,
): Promise<T> {
  const response = await fetch(modelBuilderProxyUrl(path, baseUrl), {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "x-modelbuilder-base-url": baseUrl.replace(/\/$/, ""),
    },
    body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
  })

  if (!response.ok) {
    throw new Error(await parseModelBuilderError(response))
  }

  const contentType = response.headers.get("content-type") || ""
  if (!contentType.includes("application/json")) {
    return (await response.text()) as T
  }

  return response.json() as Promise<T>
}

export function checkModelBuilderHealth(baseUrl: string) {
  return modelBuilderRequest("/health", { baseUrl })
}

export function triggerArtifactGeneration(baseUrl: string, runId: string, body: unknown) {
  return modelBuilderRequest(`/artifact-forge/runs/${encodeURIComponent(runId)}/trigger`, {
    baseUrl,
    method: "POST",
    body,
  })
}

export function invokeArtifactGeneration(baseUrl: string, runId: string, body: unknown) {
  return modelBuilderRequest(`/artifact-forge/runs/${encodeURIComponent(runId)}/invoke`, {
    baseUrl,
    method: "POST",
    body,
  })
}

export function fetchArtifactStatus(baseUrl: string, runId: string) {
  return modelBuilderRequest(`/artifact-forge/runs/${encodeURIComponent(runId)}/status`, {
    baseUrl,
  })
}

export function fetchArtifactInputSchema(
  baseUrl: string,
  scope: ArtifactTargetScope,
  identifier: string,
) {
  return modelBuilderRequest(`/${scope}/${encodeURIComponent(identifier)}/autorag/input-schema`, {
    baseUrl,
  })
}

export function invokeArtifactInference(
  baseUrl: string,
  scope: ArtifactTargetScope,
  identifier: string,
  body: unknown,
) {
  return modelBuilderRequest(`/${scope}/${encodeURIComponent(identifier)}/autorag/invoke`, {
    baseUrl,
    method: "POST",
    body,
  })
}

export function artifactDownloadUrl(baseUrl: string, runId: string): string {
  return modelBuilderProxyUrl(`/runs/${encodeURIComponent(runId)}/artifact/download`, baseUrl)
}

export function createDummyLambdaUrl(identifier: string): string {
  const safeId = identifier.trim().replace(/[^a-zA-Z0-9-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "")
  return `https://vf-${safeId || "model"}-inference.lambda-url.us-east-1.on.aws/invoke`
}
