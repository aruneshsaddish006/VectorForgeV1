"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import type { ElementType } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  ArrowLeft,
  BarChart3,
  Brain,
  CheckCircle2,
  Circle,
  Loader2,
  PlayCircle,
} from "lucide-react"
import {
  fetchOrchestratorRun,
  fetchSessionExperimentResults,
  triggerTestTrainingWorkflow,
  type ExperimentResultEvent,
  type OrchestratorRunResponse,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type StepStatus = "complete" | "running" | "pending" | "failed"

type WorkflowStep = {
  id: string
  label: string
  description: string
  icon: ElementType
  status: StepStatus
}

type ExperimentRow = {
  id: string
  designer: "autogluon" | "autorag" | "other"
  problemId: string
  round: string
  experimentId: string
  intent: string
  hypothesis: string
  primaryMetricName: string
  primaryMetricValue: string
  secondaryMetrics: Array<[string, string]>
}

const BASE_STEPS: Array<Omit<WorkflowStep, "status">> = [
  {
    id: "trigger",
    label: "Workflow trigger",
    description: "Submitting the hardcoded two-problem test request",
    icon: PlayCircle,
  },
  {
    id: "features",
    label: "Feature engineering",
    description: "Materializing datasets, resolving schema, and preparing model-ready inputs",
    icon: Brain,
  },
  {
    id: "training",
    label: "Model training and evaluation",
    description: "Running traditional ML and RAG pipeline configs, then streaming metrics by round",
    icon: BarChart3,
  },
]

const TEST_WORKFLOW_ROUNDS = 2

const ROUND_WAITING_MESSAGES = {
  autogluon: [
    "Training agent is comparing the round winner and shaping the next traditional ML config.",
    "Feature signals are being reviewed before launching the next AutoGluon batch.",
    "Model search is preparing the next set of traditional ML candidates.",
  ],
  autorag: [
    "RAG agent is reviewing retrieval quality before proposing the next pipeline config.",
    "Grounding signals are being checked before the next AutoRAG architecture starts.",
    "Retriever and generator settings are being prepared for the next RAG round.",
  ],
  other: [
    "Experiment agent is preparing the next round of candidates.",
    "Metrics are being reviewed before the next configuration starts.",
  ],
} satisfies Record<ExperimentRow["designer"], string[]>

function StatusIcon({ status }: { status: StepStatus }) {
  if (status === "complete") return <CheckCircle2 className="h-5 w-5 text-success" aria-label="Complete" />
  if (status === "running") return <Loader2 className="h-5 w-5 animate-spin text-primary" aria-label="Running" />
  if (status === "failed") return <Circle className="h-5 w-5 text-destructive" aria-label="Failed" />
  return <Circle className="h-5 w-5 text-muted-foreground/40" aria-label="Pending" />
}

function StepRow({ step, index, total }: { step: WorkflowStep; index: number; total: number }) {
  const Icon = step.icon
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            step.status === "complete" && "bg-success-soft text-success",
            step.status === "running" && "bg-info-soft text-primary",
            step.status === "failed" && "bg-destructive/10 text-destructive",
            step.status === "pending" && "bg-surface-muted text-muted-foreground",
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        {index < total - 1 && (
          <div className={cn("mt-1 w-px flex-1", step.status === "complete" ? "bg-success/30" : "bg-border")} />
        )}
      </div>
      <div className="min-w-0 pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusIcon status={step.status} />
          <span className={cn("text-sm font-semibold", step.status === "pending" ? "text-muted-foreground" : "text-foreground")}>
            {step.label}
          </span>
          {step.status === "running" && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-primary">
              Running
            </span>
          )}
          {step.status === "failed" && (
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-destructive">
              Failed
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{step.description}</p>
      </div>
    </div>
  )
}

function stepIndexFor(status: string | undefined, events: ExperimentResultEvent[]) {
  if (status === "completed") return 2
  if (status === "failed") return 0
  if (events.some((event) => String(event.payload.event_type ?? "") === "end")) return 2
  if (events.some((event) => String(event.payload.designer ?? "").toLowerCase().includes("autogluon"))) return 2
  return status === "queued" || status === "running" ? 1 : 0
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value))
}

function displayValue(value: unknown): string {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return String(value)
    return Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")
  }
  if (value === null || value === undefined || value === "") return "N/A"
  return String(value)
}

function inferProblemId(payload: Record<string, unknown>): string {
  const explicit = payload.problem_id ?? payload.problemId
  if (explicit) return String(explicit)
  const runId = String(payload.run_id ?? "")
  const match = runId.match(/(?:^|_)(prob_\d+)(?:_|$)/)
  return match?.[1] ?? "problem"
}

function normalizeExperimentEvent(event: ExperimentResultEvent): ExperimentRow | null {
  const payload = event.payload
  if (!payload.experiment_id) return null

  const config = isRecord(payload.config) ? payload.config : {}
  const metrics = isRecord(payload.metrics) ? payload.metrics : {}
  const designerText = String(payload.designer ?? "").toLowerCase()
  const designer: ExperimentRow["designer"] = designerText.includes("autorag")
    ? "autorag"
    : designerText.includes("autogluon")
      ? "autogluon"
      : "other"
  const primaryMetricName = String(metrics.primary_metric ?? config.primary_metric ?? "primary_metric")
  const primaryMetricValue = metrics.primary_metric_value ?? metrics[primaryMetricName]
  const secondarySource = isRecord(metrics.secondary_metrics)
    ? metrics.secondary_metrics
    : isRecord(metrics.evaluation)
      ? Object.fromEntries(
          Object.entries(metrics.evaluation).filter(([name]) => name !== primaryMetricName),
        )
      : {}

  return {
    id: event.id,
    designer,
    problemId: inferProblemId(payload),
    round: displayValue(payload.round),
    experimentId: String(payload.experiment_id),
    intent: String(config.intent ?? metrics.intent ?? "N/A"),
    hypothesis: String(config.hypothesis ?? metrics.hypothesis ?? "N/A"),
    primaryMetricName,
    primaryMetricValue: displayValue(primaryMetricValue),
    secondaryMetrics: Object.entries(secondarySource).map(([name, value]) => [name, displayValue(value)]),
  }
}

function groupExperimentRows(rows: ExperimentRow[]) {
  const groups = new Map<string, ExperimentRow[]>()
  for (const row of rows) {
    const key = `${row.designer}::${row.round}`
    groups.set(key, [...(groups.get(key) ?? []), row])
  }
  return Array.from(groups.entries())
    .map(([key, groupRows]) => {
      const [designer, round] = key.split("::")
      return {
        key,
        designer,
        round,
        rows: groupRows,
      }
    })
    .sort((a, b) => {
      const designerOrder = a.designer.localeCompare(b.designer)
      if (designerOrder !== 0) return designerOrder
      return Number(a.round) - Number(b.round)
    })
}

function latestRoundByDesigner(groups: ReturnType<typeof groupExperimentRows>) {
  return groups.reduce<Record<string, number>>((acc, group) => {
    const round = Number(group.round)
    acc[group.designer] = Math.max(acc[group.designer] ?? 0, Number.isFinite(round) ? round : 0)
    return acc
  }, {})
}

function waitingRoundMessage(designer: ExperimentRow["designer"], round: string) {
  const messages = ROUND_WAITING_MESSAGES[designer]
  const index = Number.isFinite(Number(round)) ? Number(round) % messages.length : 0
  return messages[index]
}

function MetricsList({ metrics }: { metrics: Array<[string, string]> }) {
  if (!metrics.length) return <span className="text-muted-foreground">N/A</span>
  return (
    <ul className="list-disc space-y-1 pl-4">
      {metrics.map(([name, value]) => (
        <li key={name}>
          <span className="font-medium text-foreground">{name}</span>: {value}
        </li>
      ))}
    </ul>
  )
}

function ExperimentTable({
  group,
  waitingForNextRound,
}: {
  group: ReturnType<typeof groupExperimentRows>[number]
  waitingForNextRound: boolean
}) {
  const isAutoRag = group.designer === "autorag"
  const title = isAutoRag ? "RAG Pipeline Config" : group.designer === "autogluon" ? "Traditional ML Config" : "Experiment Config"
  const nextRound = Number(group.round) + 1
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-foreground">
            {title} · Round {group.round}
          </p>
          <p className="text-xs text-muted-foreground">{group.rows.length} experiment result{group.rows.length === 1 ? "" : "s"}</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-xs">
          <thead className="bg-surface-muted text-[11px] uppercase text-muted-foreground">
            <tr>
              {isAutoRag ? (
                <>
                  <th className="px-4 py-3 font-semibold">Intent</th>
                  <th className="px-4 py-3 font-semibold">Hypothesis</th>
                  <th className="px-4 py-3 font-semibold">Primary metric</th>
                  <th className="px-4 py-3 font-semibold">Secondary metrics</th>
                </>
              ) : (
                <>
                  <th className="px-4 py-3 font-semibold">Experiment ID</th>
                  <th className="px-4 py-3 font-semibold">Hypothesis</th>
                  <th className="px-4 py-3 font-semibold">Primary metric</th>
                  <th className="px-4 py-3 font-semibold">Value</th>
                  <th className="px-4 py-3 font-semibold">Secondary metrics</th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {group.rows.map((row) => (
              <tr key={row.id} className="align-top">
                {isAutoRag ? (
                  <>
                    <td className="px-4 py-3 font-mono text-foreground">{row.intent}</td>
                    <td className="max-w-md px-4 py-3 text-muted-foreground">{row.hypothesis}</td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-foreground">{row.primaryMetricName}</span>
                      <span className="block font-mono text-muted-foreground">{row.primaryMetricValue}</span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground"><MetricsList metrics={row.secondaryMetrics} /></td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-3 font-mono text-foreground">{row.experimentId}</td>
                    <td className="max-w-md px-4 py-3 text-muted-foreground">{row.hypothesis}</td>
                    <td className="px-4 py-3 font-medium text-foreground">{row.primaryMetricName}</td>
                    <td className="px-4 py-3 font-mono text-muted-foreground">{row.primaryMetricValue}</td>
                    <td className="px-4 py-3 text-muted-foreground"><MetricsList metrics={row.secondaryMetrics} /></td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {waitingForNextRound && (
        <div className="border-t border-border bg-surface-muted px-4 py-3">
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-hidden="true" />
            <div>
              <p className="font-medium text-foreground">Waiting for Round {nextRound} results...</p>
              <p className="mt-0.5">{waitingRoundMessage(group.designer as ExperimentRow["designer"], group.round)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RunWorkflowContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const sessionId = searchParams.get("session") ?? "unknown"
  const runToken = searchParams.get("run") ?? "manual"
  const [orchId, setOrchId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<OrchestratorRunResponse | null>(null)
  const [events, setEvents] = useState<ExperimentResultEvent[]>([])
  const [cursor, setCursor] = useState("0-0")
  const [error, setError] = useState<string | null>(null)
  const [triggered, setTriggered] = useState(false)

  useEffect(() => {
    if (!sessionId || sessionId === "unknown") return
    let cancelled = false

    async function trigger() {
      setError(null)
      try {
        const storageKey = `vectorforge.workflow.${sessionId}.${runToken}.orch_id`
        const cursorKey = `vectorforge.workflow.${sessionId}.${runToken}.stream_cursor`
        const existingOrchId = window.sessionStorage.getItem(storageKey)
        if (existingOrchId?.startsWith("orch_")) {
          const existingCursor = window.sessionStorage.getItem(cursorKey)
          if (existingCursor) setCursor(existingCursor)
          setOrchId(existingOrchId)
          setTriggered(true)
          return
        }

        const streamCursor = `${Date.now()}-0`
        window.sessionStorage.setItem(cursorKey, streamCursor)
        setCursor(streamCursor)
        const response = await triggerTestTrainingWorkflow(sessionId)
        if (cancelled) return
        window.sessionStorage.setItem(storageKey, response.orch_id)
        setOrchId(response.orch_id)
        setTriggered(true)
        setRunStatus(response)
      } catch (err) {
        if (!cancelled) {
          window.sessionStorage.removeItem(`vectorforge.workflow.${sessionId}.${runToken}.orch_id`)
          window.sessionStorage.removeItem(`vectorforge.workflow.${sessionId}.${runToken}.stream_cursor`)
          setError((err as Error).message)
        }
      }
    }

    void trigger()
    return () => {
      cancelled = true
    }
  }, [runToken, sessionId])

  useEffect(() => {
    if (!sessionId || sessionId === "unknown") return
    if (!triggered) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    async function poll() {
      let latestStatus = runStatus?.status
      try {
        const [status, results] = await Promise.all([
          orchId?.startsWith("orch_")
            ? fetchOrchestratorRun(orchId)
            : fetchOrchestratorRun(sessionId).catch(() => null),
          fetchSessionExperimentResults(sessionId, cursor, { count: 100 }),
        ])
        if (cancelled) return
        if (status) {
          latestStatus = status.status
          setRunStatus(status)
          if (status.orch_id && status.orch_id !== orchId) setOrchId(status.orch_id)
        }
        if (results.cursor) setCursor(results.cursor)
        if (results.events.length) {
          setEvents((current) => {
            const seen = new Set(current.map((event) => event.id))
            return [...current, ...results.events.filter((event) => !seen.has(event.id))]
          })
        }
      } catch (err) {
        if (!cancelled && triggered) setError((err as Error).message)
      }

      if (!cancelled && latestStatus !== "completed" && latestStatus !== "failed") {
        timer = setTimeout(poll, 3000)
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [cursor, orchId, runStatus?.status, sessionId, triggered])

  const activeRunId =
    typeof runStatus?.result?.run_id === "string"
      ? runStatus.result.run_id
      : typeof runStatus?.run_id === "string"
        ? runStatus.run_id
        : null
  const scopedEvents = useMemo(() => {
    if (!activeRunId) return []
    return events.filter((event) => {
      const eventRunId = String(event.payload.run_id ?? "")
      return eventRunId === "autogluon" || eventRunId === activeRunId || eventRunId.startsWith(`${activeRunId}_`)
    })
  }, [activeRunId, events])
  const activeIndex = stepIndexFor(runStatus?.status, scopedEvents)
  const steps = useMemo<WorkflowStep[]>(
    () =>
      BASE_STEPS.map((step, index) => ({
        ...step,
        status:
          runStatus?.status === "failed"
            ? index === activeIndex
              ? "failed"
              : index < activeIndex
                ? "complete"
                : "pending"
            : index < activeIndex
              ? "complete"
              : index === activeIndex
                ? runStatus?.status === "completed"
                  ? "complete"
                  : "running"
                : "pending",
      })),
    [activeIndex, runStatus?.status],
  )
  const currentStep = steps.find((step) => step.status === "running")
  const experimentGroups = groupExperimentRows(
    scopedEvents
      .map((event) => normalizeExperimentEvent(event))
      .filter((row): row is ExperimentRow => Boolean(row)),
  )
  const latestRounds = latestRoundByDesigner(experimentGroups)
  const isRunActive = runStatus?.status !== "completed" && runStatus?.status !== "failed"
  const activityMessage = scopedEvents.length
    ? "Agents are streaming evaluated configs into the results tables."
    : orchId?.startsWith("orch_")
      ? "Agents are warming up the training queue and waiting for first metrics."
      : "Submitting the hardcoded two-round workflow request to modelbuilder."

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-canvas p-3 text-foreground sm:p-4">
      <div className="flex min-h-0 flex-1 items-start justify-center overflow-y-auto py-8">
        <div className="w-full max-w-6xl space-y-6 px-4">
          <div>
            <button
              type="button"
              onClick={() => router.back()}
              className="mb-4 flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to plan
            </button>
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                <PlayCircle className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h1 className="text-xl font-bold text-foreground">
                  {runStatus?.status === "completed" ? "Workflow completed" : runStatus?.status === "failed" ? "Workflow failed" : "Workflow running"}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {currentStep ? `Currently: ${currentStep.label}` : "Waiting for modelbuilder status"}
                </p>
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-border bg-surface">
            <div className="border-b border-border px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-medium uppercase text-muted-foreground">Session ID</p>
                  <p className="mt-0.5 break-all font-mono text-xs text-foreground">{sessionId}</p>
                </div>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-[11px] font-semibold uppercase text-primary">
                  {runStatus?.status ?? "queued"}
                </span>
              </div>
            </div>
            <div className="grid gap-0 border-b border-border text-xs sm:grid-cols-4">
              <div className="border-border px-4 py-3 sm:border-r">
                <p className="text-muted-foreground">Orchestrator</p>
                <p className="mt-1 truncate font-mono text-foreground">{orchId ?? "starting"}</p>
              </div>
              <div className="border-border px-4 py-3 sm:border-r">
                <p className="text-muted-foreground">Test plan</p>
                <p className="mt-1 font-mono text-foreground">2 rounds x 2 configs</p>
              </div>
              <div className="border-border px-4 py-3 sm:border-r">
                <p className="text-muted-foreground">Stream cursor</p>
                <p className="mt-1 font-mono text-foreground">{cursor}</p>
              </div>
              <div className="px-4 py-3">
                <p className="text-muted-foreground">Events</p>
                <p className="mt-1 font-mono text-foreground">{scopedEvents.length}</p>
              </div>
            </div>
            <div className="flex items-start gap-2 px-4 py-3 text-xs text-muted-foreground">
              {isRunActive ? (
                <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" aria-hidden="true" />
              )}
              <div>
                <p className="font-medium text-foreground">Agent activity</p>
                <p className="mt-0.5">{activityMessage}</p>
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="rounded-xl border border-border bg-surface px-5 py-5">
            <p className="mb-4 text-sm font-semibold text-foreground">Execution pipeline</p>
            {steps.map((step, i) => (
              <StepRow key={step.id} step={step} index={i} total={steps.length} />
            ))}
          </div>

          <div className="space-y-4">
            <div>
              <p className="text-sm font-semibold text-foreground">Experiment results</p>
              <p className="text-xs text-muted-foreground">
                Results are grouped by config type and round as stream events arrive.
              </p>
            </div>
            {experimentGroups.length === 0 ? (
              <div className="rounded-xl border border-border bg-surface px-4 py-4 text-xs text-muted-foreground">
                <div className="flex items-start gap-2">
                  <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-hidden="true" />
                  <div>
                    <p className="font-medium text-foreground">Waiting for first experiment result...</p>
                    <p className="mt-1">
                      The training agent has the request. Metrics will appear here as soon as a config finishes evaluation.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              experimentGroups.map((group) => {
                const round = Number(group.round)
                const waitingForNextRound =
                  isRunActive
                  && Number.isFinite(round)
                  && round === latestRounds[group.designer]
                  && round < TEST_WORKFLOW_ROUNDS
                return (
                  <ExperimentTable
                    key={group.key}
                    group={group}
                    waitingForNextRound={waitingForNextRound}
                  />
                )
              })
            )}
          </div>

        </div>
      </div>
    </div>
  )
}

export default function RunWorkflowPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-dvh items-center justify-center bg-canvas">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <RunWorkflowContent />
    </Suspense>
  )
}
