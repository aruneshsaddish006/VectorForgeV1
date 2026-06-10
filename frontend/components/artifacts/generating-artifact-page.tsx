"use client"

import * as React from "react"
import Link from "next/link"
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  CircleAlert,
  CloudCog,
  Copy,
  Download,
  FileArchive,
  Loader2,
  Package,
  Play,
  Rocket,
  Send,
  Server,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  DEFAULT_MODEL_API_BASE_URL,
  artifactDownloadUrl,
  checkModelBuilderHealth,
  createDummyLambdaUrl,
  fetchArtifactStatus,
  invokeArtifactInference,
} from "@/lib/modelbuilder"

type BusyAction = "health" | "artifact" | "status" | "deploy" | "inference" | null
type StepState = "idle" | "ready" | "running" | "complete" | "error"

type TimelineItem = {
  label: string
  detail: string
  state: Exclude<StepState, "idle" | "ready">
}

const DEFAULT_INFERENCE_BODY = JSON.stringify(
  {
    question: "What is the model prediction or answer for this input?",
    input: [
      {
        feature_name: "value",
      },
    ],
  },
  null,
  2,
)

function parseJson(text: string): unknown {
  const trimmed = text.trim()
  if (!trimmed) return {}
  return JSON.parse(trimmed)
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function getStatus(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null
  const record = payload as Record<string, unknown>
  const status = record.artifact_status || record.status || record.smoke_status
  return typeof status === "string" ? status : null
}

export function GeneratingArtifactPage() {
  const [baseUrl, setBaseUrl] = React.useState(DEFAULT_MODEL_API_BASE_URL)
  const [sessionId, setSessionId] = React.useState("")
  const [busyAction, setBusyAction] = React.useState<BusyAction>(null)
  const [healthState, setHealthState] = React.useState<StepState>("idle")
  const [artifactState, setArtifactState] = React.useState<StepState>("idle")
  const [deploymentState, setDeploymentState] = React.useState<StepState>("idle")
  const [inferenceState, setInferenceState] = React.useState<StepState>("idle")
  const [artifactStatus, setArtifactStatus] = React.useState("Not generated")
  const [deployApproved, setDeployApproved] = React.useState(false)
  const [lambdaUrl, setLambdaUrl] = React.useState("")
  const [inferenceBody, setInferenceBody] = React.useState(DEFAULT_INFERENCE_BODY)
  const [lastResponse, setLastResponse] = React.useState<unknown>({
    message: "Enter a model session_id to begin.",
  })
  const [error, setError] = React.useState<string | null>(null)
  const [timeline, setTimeline] = React.useState<TimelineItem[]>([])

  const normalizedBaseUrl = baseUrl.trim().replace(/\/$/, "")
  const modelSessionId = sessionId.trim()
  const canUseModel = Boolean(modelSessionId) && Boolean(normalizedBaseUrl) && !busyAction
  const responseText = React.useMemo(() => formatJson(lastResponse), [lastResponse])

  function addTimeline(label: string, detail: string, state: TimelineItem["state"]) {
    setTimeline((items) => [{ label, detail, state }, ...items].slice(0, 5))
  }

  async function runAction<T>(action: Exclude<BusyAction, null>, fn: () => Promise<T>): Promise<T | null> {
    setBusyAction(action)
    setError(null)

    try {
      const result = await fn()
      setLastResponse(result)
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed."
      setError(message)
      setLastResponse({ error: message })
      return null
    } finally {
      setBusyAction(null)
    }
  }

  async function handleHealth() {
    setHealthState("running")
    const result = await runAction("health", () => checkModelBuilderHealth(normalizedBaseUrl))
    setHealthState(result ? "complete" : "error")
    addTimeline("Modelbuilder health", result ? "Service responded successfully." : "Health check failed.", result ? "complete" : "error")
  }

  async function handleGenerateAndDownload() {
    setArtifactState("running")
    const result = await runAction("artifact", async () => {
      window.open(artifactDownloadUrl(normalizedBaseUrl, modelSessionId), "_blank", "noopener,noreferrer")
      return {
        action: "download_or_generate",
        download_url: artifactDownloadUrl(normalizedBaseUrl, modelSessionId),
        note: "Download route will return existing artifacts or generate missing child artifacts before responding.",
      }
    })

    if (result) {
      setArtifactState("complete")
      setArtifactStatus(getStatus(result) || "Download requested")
      addTimeline("Artifact zip", "Generation requested and zip download opened.", "complete")
    } else {
      setArtifactState("error")
      addTimeline("Artifact zip", "Could not generate or download the model codebase.", "error")
    }
  }

  async function handleCheckArtifactStatus() {
    setArtifactState("running")
    const result = await runAction("status", () => fetchArtifactStatus(normalizedBaseUrl, modelSessionId))
    const status = getStatus(result)
    setArtifactStatus(status || (result ? "Status loaded" : "Status failed"))
    setArtifactState(result ? "complete" : "error")
    addTimeline("Artifact status", status || (result ? "Status loaded." : "Status failed."), result ? "complete" : "error")
  }

  async function handleApproveDeploy() {
    setDeployApproved(true)
    setDeploymentState("running")
    const result = await runAction("deploy", async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 850))
      const url = createDummyLambdaUrl(modelSessionId)
      setLambdaUrl(url)
      return {
        status: "approved",
        deployment_mode: "dummy_aws_lambda_url",
        model_session_id: modelSessionId,
        lambda_url: url,
      }
    })

    setDeploymentState(result ? "complete" : "error")
    addTimeline("Deployment approval", result ? "Dummy Lambda endpoint prepared." : "Deployment approval failed.", result ? "complete" : "error")
  }

  async function handleInference() {
    setInferenceState("running")
    const result = await runAction("inference", () =>
      invokeArtifactInference(normalizedBaseUrl, "sessions", modelSessionId, parseJson(inferenceBody)),
    )
    setInferenceState(result ? "complete" : "error")
    addTimeline("Inference", result ? "Inference request completed." : "Inference request failed.", result ? "complete" : "error")
  }

  function copyText(text: string) {
    navigator.clipboard.writeText(text).catch(() => undefined)
  }

  return (
    <div className="flex min-h-dvh w-full flex-col bg-canvas p-3 text-foreground sm:p-4">
      <header className="app-panel flex min-h-20 shrink-0 flex-wrap items-center justify-between gap-3 rounded-[24px] px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/dashboard"
            className="app-control flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-muted-foreground transition hover:text-foreground"
            aria-label="Back to dashboard"
            title="Back to dashboard"
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
          </Link>
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
            <Package className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h1 className="truncate font-heading text-2xl font-bold tracking-tight text-foreground">
              Generating Artifact
            </h1>
            <p className="truncate text-xs font-semibold uppercase text-muted-foreground">
              Model codebase, deployment approval, and inference
            </p>
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-2">
          <StateBadge state={healthState} label={healthState === "complete" ? "Online" : "Modelbuilder"} />
          <Button variant="outline" onClick={handleHealth} disabled={!normalizedBaseUrl || busyAction === "health"} className="rounded-full">
            {busyAction === "health" ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Server className="h-4 w-4" aria-hidden="true" />
            )}
            Health
          </Button>
        </div>
      </header>

      <main className="scroll-thin min-h-0 flex-1 overflow-y-auto py-4">
        <div className="mx-auto grid max-w-7xl gap-4">
          <section className="app-panel-raised rounded-[28px] p-5 sm:p-6">
            <div className="grid gap-4 lg:grid-cols-[1fr_17rem]">
              <div>
                <p className="text-sm font-semibold text-muted-foreground">Model session</p>
                <h2 className="mt-1 font-heading text-3xl font-bold tracking-tight text-foreground">
                  Enter the model session_id
                </h2>
                <div className="mt-5 grid gap-3 md:grid-cols-[1fr_16rem]">
                  <label className="block">
                    <span className="text-sm font-medium text-foreground">Model session_id</span>
                    <input
                      value={sessionId}
                      onChange={(event) => setSessionId(event.target.value)}
                      placeholder="f1050d64_622614c6_d172aafc"
                      className="app-control mt-1.5 h-12 w-full rounded-full px-4 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                    />
                  </label>
                  <label className="block">
                    <span className="text-sm font-medium text-foreground">Modelbuilder URL</span>
                    <input
                      value={baseUrl}
                      onChange={(event) => setBaseUrl(event.target.value)}
                      placeholder="http://localhost:8000"
                      className="app-control mt-1.5 h-12 w-full rounded-full px-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                    />
                  </label>
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-surface-muted p-4">
                <p className="text-xs font-bold uppercase text-muted-foreground">Current state</p>
                <div className="mt-4 space-y-3">
                  <MiniStep label="Artifact" state={artifactState} />
                  <MiniStep label="Deploy" state={deploymentState} />
                  <MiniStep label="Inference" state={inferenceState} />
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-3">
            <WorkflowCard
              icon={FileArchive}
              title="Download model codebase"
              state={artifactState}
              accent="primary"
              footer={
                <div className="flex flex-wrap gap-2">
                  <Button onClick={handleGenerateAndDownload} disabled={!canUseModel || busyAction === "artifact"} className="rounded-full">
                    {busyAction === "artifact" ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Download className="h-4 w-4" aria-hidden="true" />
                    )}
                    Generate zip
                  </Button>
                  <Button variant="outline" onClick={handleCheckArtifactStatus} disabled={!canUseModel || busyAction === "status"} className="rounded-full">
                    Check status
                  </Button>
                </div>
              }
            >
              <p className="text-sm leading-6 text-muted-foreground">
                Generates the artifact from modelbuilder and opens the sealed model codebase zip.
              </p>
              <div className="mt-4 rounded-2xl bg-surface-muted p-3">
                <p className="text-xs font-bold uppercase text-muted-foreground">Artifact status</p>
                <p className="mt-1 break-all text-sm font-semibold text-foreground">{artifactStatus}</p>
              </div>
            </WorkflowCard>

            <WorkflowCard
              icon={ShieldCheck}
              title="Approve deployment"
              state={deploymentState}
              accent="success"
              footer={
                <Button onClick={handleApproveDeploy} disabled={!canUseModel || busyAction === "deploy"} variant="success" className="rounded-full">
                  {busyAction === "deploy" ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Rocket className="h-4 w-4" aria-hidden="true" />
                  )}
                  Approve
                </Button>
              }
            >
              <p className="text-sm leading-6 text-muted-foreground">
                Approval prepares the deployment screen and provisions a placeholder Lambda endpoint for testing.
              </p>
              <div className="mt-4 flex items-center gap-2 rounded-2xl bg-surface-muted p-3 text-sm">
                {deployApproved ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                )}
                <span className="font-semibold text-foreground">
                  {deployApproved ? "Deployment approved" : "Waiting for approval"}
                </span>
              </div>
            </WorkflowCard>

            <WorkflowCard
              icon={CloudCog}
              title="Lambda endpoint"
              state={deploymentState === "complete" ? "complete" : "idle"}
              accent="info"
              footer={
                <Button
                  variant="outline"
                  onClick={() => copyText(lambdaUrl)}
                  disabled={!lambdaUrl}
                  className="rounded-full"
                >
                  <Copy className="h-4 w-4" aria-hidden="true" />
                  Copy URL
                </Button>
              }
            >
              <p className="text-sm leading-6 text-muted-foreground">
                The deployment card exposes the API URL your frontend or QA flow can target.
              </p>
              <div className="mt-4 rounded-2xl border border-border bg-surface-muted p-3">
                <p className="text-xs font-bold uppercase text-muted-foreground">Dummy AWS Lambda URL</p>
                <p className="mt-2 break-all font-mono text-xs font-semibold text-foreground">
                  {lambdaUrl || "Approve deployment to generate a dummy endpoint."}
                </p>
              </div>
            </WorkflowCard>
          </section>

          <section className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="app-panel-raised rounded-[28px] p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-primary" aria-hidden="true" />
                    <h2 className="font-heading text-2xl font-bold text-foreground">Run inference</h2>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Use the model session artifact endpoint while showing the Lambda URL as the deployment target.
                  </p>
                </div>
                <StateBadge state={inferenceState} label="Inference" />
              </div>

              <textarea
                value={inferenceBody}
                onChange={(event) => setInferenceBody(event.target.value)}
                spellCheck={false}
                className="scroll-thin mt-4 min-h-56 w-full resize-none rounded-2xl border border-border bg-surface-muted p-4 font-mono text-xs leading-6 text-foreground outline-none transition focus:border-primary"
              />

              <div className="mt-4 flex flex-wrap justify-end gap-2">
                <Button variant="outline" onClick={() => setInferenceBody(DEFAULT_INFERENCE_BODY)} className="rounded-full">
                  Reset
                </Button>
                <Button onClick={handleInference} disabled={!canUseModel || busyAction === "inference"} className="rounded-full">
                  {busyAction === "inference" ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Play className="h-4 w-4" aria-hidden="true" />
                  )}
                  Run inference
                </Button>
              </div>
            </div>

            <div className="app-panel-raised rounded-[28px] p-5 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Terminal className="h-5 w-5 text-primary" aria-hidden="true" />
                  <h2 className="font-heading text-2xl font-bold text-foreground">Response</h2>
                </div>
                <Button variant="outline" onClick={() => copyText(responseText)} className="rounded-full">
                  <Copy className="h-4 w-4" aria-hidden="true" />
                  Copy
                </Button>
              </div>

              {error && (
                <div className="mt-4 rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
                  {error}
                </div>
              )}

              <pre className="scroll-thin mt-4 max-h-[26rem] overflow-auto rounded-2xl bg-surface-muted p-4 font-mono text-xs leading-6 text-foreground">
                {responseText}
              </pre>
            </div>
          </section>

          <section className="app-panel-raised rounded-[28px] p-5 sm:p-6">
            <p className="text-sm font-semibold text-muted-foreground">Session activity</p>
            <div className="mt-4 grid gap-3 md:grid-cols-5">
              {timeline.length === 0 ? (
                <div className="rounded-2xl bg-surface-muted p-4 text-sm text-muted-foreground md:col-span-5">
                  Activity from generation, deployment approval, and inference will appear here.
                </div>
              ) : (
                timeline.map((item, index) => (
                  <div key={`${item.label}-${index}`} className="rounded-2xl border border-border bg-surface-muted p-4">
                    <div className="flex items-center gap-2">
                      {item.state === "complete" ? (
                        <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
                      ) : item.state === "running" ? (
                        <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
                      ) : (
                        <CircleAlert className="h-4 w-4 text-error" aria-hidden="true" />
                      )}
                      <p className="truncate text-sm font-bold text-foreground">{item.label}</p>
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">{item.detail}</p>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

function WorkflowCard({
  icon: Icon,
  title,
  state,
  accent,
  children,
  footer,
}: {
  icon: React.ElementType
  title: string
  state: StepState
  accent: "primary" | "success" | "info"
  children: React.ReactNode
  footer: React.ReactNode
}) {
  return (
    <article className="app-panel-raised flex min-h-72 flex-col rounded-[28px] p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <span
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-2xl",
            accent === "primary" && "bg-primary text-primary-foreground",
            accent === "success" && "bg-success text-white",
            accent === "info" && "bg-info-soft text-info",
          )}
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <StateBadge state={state} label={state === "complete" ? "Ready" : state === "running" ? "Running" : "Pending"} />
      </div>
      <h3 className="mt-5 font-heading text-2xl font-bold text-foreground">{title}</h3>
      <div className="mt-3 flex-1">{children}</div>
      <div className="mt-5">{footer}</div>
    </article>
  )
}

function MiniStep({ label, state }: { label: string; state: StepState }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <StateBadge state={state} label={state === "complete" ? "Done" : state === "running" ? "Running" : "Pending"} compact />
    </div>
  )
}

function StateBadge({
  state,
  label,
  compact = false,
}: {
  state: StepState
  label: string
  compact?: boolean
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-bold",
        compact ? "px-2.5 py-1 text-[11px]" : "h-9 px-3 text-xs",
        (state === "idle" || state === "ready") && "bg-surface-muted text-muted-foreground",
        state === "running" && "bg-info-soft text-info",
        state === "complete" && "bg-success-soft text-success",
        state === "error" && "bg-error-soft text-error",
      )}
    >
      {state === "running" ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : state === "complete" ? (
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
      ) : state === "error" ? (
        <CircleAlert className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Circle className="h-4 w-4" aria-hidden="true" />
      )}
      {label}
    </span>
  )
}
