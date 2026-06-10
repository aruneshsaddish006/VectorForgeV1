const DEFAULT_MODEL_BUILDER_URL =
  process.env.MODEL_API_URL ||
  process.env.NEXT_PUBLIC_MODEL_API_URL ||
  "http://localhost:8000"

function resolveBaseUrl(request: Request): string {
  const incomingUrl = new URL(request.url)
  const requestedBase =
    request.headers.get("x-model-builder-base-url") ||
    incomingUrl.searchParams.get("baseUrl") ||
    DEFAULT_MODEL_BUILDER_URL

  const parsed = new URL(requestedBase)
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Model Builder URL must start with http:// or https://")
  }

  parsed.pathname = parsed.pathname.replace(/\/$/, "")
  parsed.search = ""
  parsed.hash = ""
  return parsed.toString().replace(/\/$/, "")
}

async function proxyModelBuilder(request: Request) {
  let baseUrl: string
  try {
    baseUrl = resolveBaseUrl(request)
  } catch (error) {
    return Response.json(
      { detail: error instanceof Error ? error.message : "Invalid model-builder URL" },
      { status: 400 },
    )
  }

  const incomingUrl = new URL(request.url)
  incomingUrl.searchParams.delete("baseUrl")

  const targetUrl = new URL(baseUrl)
  targetUrl.search = incomingUrl.search

  const headers = new Headers()
  const accept = request.headers.get("accept")
  const contentType = request.headers.get("content-type")
  if (accept) headers.set("accept", accept)
  if (contentType) headers.set("content-type", contentType)

  const method = request.method.toUpperCase()
  const response = await fetch(targetUrl, {
    method,
    headers,
    body: method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
  })

  const responseHeaders = new Headers()
  for (const key of ["content-type", "content-disposition", "cache-control"]) {
    const value = response.headers.get(key)
    if (value) responseHeaders.set(key, value)
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  })
}

export async function GET(request: Request) {
  return proxyModelBuilder(request)
}

export async function POST(request: Request) {
  return proxyModelBuilder(request)
}

export async function PUT(request: Request) {
  return proxyModelBuilder(request)
}

export async function PATCH(request: Request) {
  return proxyModelBuilder(request)
}

export async function DELETE(request: Request) {
  return proxyModelBuilder(request)
}
