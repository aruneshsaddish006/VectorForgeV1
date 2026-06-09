"use client"

import { useEffect, useRef, useState, type ElementType } from "react"
import { Cpu, Database, Loader2, Rocket, ShieldCheck, Trash2 } from "lucide-react"
import { UserMessage, AgentMessage, SystemCardSlot } from "./messages"
import { Composer } from "./composer"
import { StrategyCard } from "@/components/cards/strategy-card"
import { DataSourceCard } from "@/components/cards/data-source-card"
import { DecomposerCard, type DecomposerCardData } from "@/components/cards/decomposer-card"
import { DataUploadCard } from "@/components/cards/data-upload-card"
import { ExaBuilderCard } from "@/components/cards/exa-builder-card"
import { SchemaConfirmCard } from "@/components/cards/schema-confirm-card"
import { TrainingCard } from "@/components/cards/training-card"
import { RagCard } from "@/components/cards/rag-card"
import { DeploymentCard } from "@/components/cards/deployment-card"
import { BillingApprovalCard } from "@/components/cards/billing-approval-card"
import {
  fetchDemoWorkspace,
  fetchProjectAssets,
  getConversationState,
  respondToInterrupt,
  streamRespondToInterrupt,
  startConversation,
  uploadDataset,
  type Project,
  type ProjectAssets,
  type Workspace,
} from "@/lib/api"
import type { ConversationMessage, ConversationSession, DemoWorkspace } from "@/lib/types"

// ---------------------------------------------------------------------------
// Session ID helpers
// ---------------------------------------------------------------------------

const DEFAULT_WORKSPACE_ID = "default_workspace"
const DEFAULT_PROJECT_ID = "default_project"

/**
 * Deterministic session ID scoped to a specific user + workspace + project.
 * Falls back to default IDs so a session can always be created, even before
 * workspace/project management has been set up by the other developer.
 */
function buildSessionId(
  userId: string,
  workspaceId: string,
  projectId: string,
): string {
  return `${userId}_${workspaceId}_${projectId}`
}

/** Merge server snapshot into client session.
 *  The server snapshot is authoritative for status/interrupt.
 *  For messages, keep whichever list is longer — the server snapshot can be
 *  sparse when a node interrupted before returning its state update. */
function mergeSession(
  prev: ConversationSession | null,
  updated: ConversationSession,
): ConversationSession {
  const messages =
    updated.messages.length >= (prev?.messages.length ?? 0)
      ? updated.messages
      : (prev?.messages ?? updated.messages)
  return { ...updated, messages }
}

function getStoredUserId(): string {
  if (typeof window === "undefined") return "anonymous"
  try {
    const raw = window.localStorage.getItem("forge_ai_user")
    const user = raw ? JSON.parse(raw) : null
    return user?.id ?? "anonymous"
  } catch {
    return "anonymous"
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch {
    return ""
  }
}

// ---------------------------------------------------------------------------
// ChatThread
// ---------------------------------------------------------------------------

export function ChatThread({
  selectedWorkspace,
  selectedProject,
}: {
  selectedWorkspace: Workspace | null
  selectedProject: Project | null
}) {
  // Demo / mock-backend state (existing behaviour — unchanged)
  const [workspace, setWorkspace] = useState<DemoWorkspace | null>(null)
  const [assets, setAssets] = useState<ProjectAssets | null>(null)
  const [apiState, setApiState] = useState<"loading" | "connected" | "fallback">("loading")

  // Conversational agent state
  const [session, setSession] = useState<ConversationSession | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [convStarted, setConvStarted] = useState(false)
  const [convLoading, setConvLoading] = useState(false)
  const [convError, setConvError] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)

  // Load demo workspace data (existing behaviour — unchanged)
  useEffect(() => {
    const controller = new AbortController()
    fetchDemoWorkspace(controller.signal)
      .then((data) => { setWorkspace(data); setApiState("connected") })
      .catch(() => { setApiState("fallback") })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!selectedWorkspace || !selectedProject) { setAssets(null); return }
    fetchProjectAssets(selectedWorkspace.id, selectedProject.id)
      .then(setAssets)
      .catch(() => setAssets(null))
  }, [selectedWorkspace?.id, selectedProject?.id])

  // Build deterministic session ID on every workspace/project change.
  // Falls back to defaults so a session always exists even before the other
  // developer wires up full user/workspace/project management.
  useEffect(() => {
    const userId = getStoredUserId()
    const wsId = selectedWorkspace?.id ?? DEFAULT_WORKSPACE_ID
    const projId = selectedProject?.id ?? DEFAULT_PROJECT_ID
    const sid = buildSessionId(userId, wsId, projId)
    setSessionId(sid)

    // Try to hydrate an existing session for this combination.
    // Only clear client state on failure if we don't already have messages —
    // a server hot-reload loses MemorySaver state but the client still has
    // the rendered conversation; don't wipe it.
    setConvLoading(true)
    getConversationState(sid)
      .then((s) => { setSession(s); setConvStarted(true) })
      .catch(() => {
        setSession((prev) => {
          if (prev && prev.messages.length > 0) return prev
          return null
        })
        setConvStarted((prev) => {
          if (prev) return prev
          return false
        })
      })
      .finally(() => setConvLoading(false))
  }, [selectedWorkspace?.id, selectedProject?.id])

  // Auto-scroll when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [session?.messages.length])

  async function handleSend(text: string) {
    if (!sessionId || convLoading) return
    setConvError(null)
    setConvLoading(true)

    // Optimistic user message so the UI responds immediately
    const userMsg: ConversationMessage = {
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    }
    setSession((prev: ConversationSession | null) =>
      prev
        ? { ...prev, messages: [...prev.messages, userMsg], interrupt: null }
        : { sessionId: sessionId!, status: "intake", messages: [userMsg], interrupt: null },
    )

    try {
      if (!convStarted) {
        const updated = await startConversation(sessionId, text)
        setConvStarted(true)
        setSession(updated)
      } else {
        await new Promise<void>((resolve, reject) => {
          streamRespondToInterrupt(sessionId, { answers: { "0": text } }, {
            onMessage(msg) {
              setSession((prev) =>
                prev ? { ...prev, messages: [...prev.messages, msg] } : prev,
              )
            },
            onComplete(updated) {
              setSession((prev) => mergeSession(prev, updated))
              resolve()
            },
            onError(detail) { reject(new Error(detail)) },
          })
        })
      }
    } catch (err) {
      setConvError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setConvLoading(false)
    }
  }

  async function handleInterruptAction(payload: Record<string, unknown>) {
    if (!sessionId || convLoading) return
    setConvError(null)
    setConvLoading(true)
    try {
      await new Promise<void>((resolve, reject) => {
        streamRespondToInterrupt(sessionId, payload, {
          onMessage(msg) {
            setSession((prev) =>
              prev ? { ...prev, messages: [...prev.messages, msg] } : prev,
            )
          },
          onComplete(updated) {
            setSession((prev) => mergeSession(prev, updated))
            resolve()
          },
          onError(detail) { reject(new Error(detail)) },
        })
      })
    } catch (err) {
      setConvError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setConvLoading(false)
    }
  }

  async function handleFileUpload(probId: string, file: File) {
    if (!sessionId || convLoading) return
    setConvError(null)
    setConvLoading(true)
    try {
      await uploadDataset(sessionId, probId, file)
      setSession(await getConversationState(sessionId))
    } catch (err) {
      setConvError(err instanceof Error ? err.message : "Upload failed.")
    } finally {
      setConvLoading(false)
    }
  }

  // Paperclip in Composer → upload directly when awaiting_upload, otherwise no-op
  function handleComposerFile(file: File) {
    const probId = session?.interrupt?.problemId
    const itype = session?.interrupt?.type
    if (!probId) return
    if (itype === "awaiting_upload") {
      handleFileUpload(probId, file)
    } else if (itype === "dataset_source_choice") {
      handleChoiceAndUpload(file, probId)
    }
  }

  function handleClearChat() {
    const userId = getStoredUserId()
    const wsId = selectedWorkspace?.id ?? DEFAULT_WORKSPACE_ID
    const projId = selectedProject?.id ?? DEFAULT_PROJECT_ID
    setSessionId(`${buildSessionId(userId, wsId, projId)}_${Date.now()}`)
    setSession(null)
    setConvStarted(false)
    setConvError(null)
  }

  // Two-step upload: send choice=upload then immediately upload the file
  async function handleChoiceAndUpload(file: File, probId: string) {
    if (!sessionId || convLoading) return
    setConvError(null)
    setConvLoading(true)
    try {
      await respondToInterrupt(sessionId, { choice: "upload" })
      await uploadDataset(sessionId, probId, file)
      setSession(await getConversationState(sessionId))
    } catch (err) {
      setConvError(err instanceof Error ? err.message : "Upload failed.")
    } finally {
      setConvLoading(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Empty states — unchanged from original
  // ---------------------------------------------------------------------------

  if (!selectedWorkspace) {
    return (
      <EmptyWorkflowState
        title="Create your first workspace"
        text="After login, start by creating a workspace for your company, business unit, or AI initiative. Projects, datasets, and models are scoped inside a workspace."
      />
    )
  }

  if (!selectedProject) {
    return (
      <EmptyWorkflowState
        title={`Create a project in ${selectedWorkspace.name}`}
        text="Projects organize the AI product workflow. Once a project exists, Forge AI will show its datasets, models, approvals, and launch readiness."
      />
    )
  }

  const isComplete = session?.status === "complete"

  return (
    <div className="relative flex h-full flex-col">
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <section className="app-panel-raised overflow-hidden rounded-[28px] p-6 sm:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-muted-foreground">Welcome back</p>
                <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                  {selectedProject.name}
                </h1>
                <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                  {selectedWorkspace.name} brings data sourcing, model search, retrieval, approvals, and deployment into one guided AI product workflow.
                </p>
              </div>
              <div className="grid min-w-0 grid-cols-2 gap-3 sm:grid-cols-4 lg:w-[440px]">
                <Metric icon={Database} label="Dataset" value={assets?.dataset?.rowCount ? `${assets.dataset.rowCount}` : "4,820"} />
                <Metric icon={Cpu} label="Best AUC" value={assets?.training?.metrics.bestRocAuc || "0.921"} />
                <Metric icon={ShieldCheck} label="Status" value="Approval" />
                <Metric icon={Rocket} label="Launch" value="Ready" />
              </div>
            </div>
          </section>

          <div className="flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Today &middot; {selectedProject.name}
            </span>
            <span className="h-px flex-1 bg-border" />
            {convStarted && (
              <button
                type="button"
                onClick={handleClearChat}
                className="flex shrink-0 items-center gap-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-destructive"
                title="Clear conversation"
              >
                <Trash2 className="h-3 w-3" aria-hidden="true" />
                Clear chat
              </button>
            )}
          </div>

          <div className="app-control mx-auto rounded-full px-4 py-1.5 text-[11px] font-semibold text-muted-foreground">
            {selectedWorkspace.name} / {selectedProject.name} &middot;{" "}
            {apiState === "connected"
              ? "Mock backend connected"
              : apiState === "fallback"
                ? "Using local UI fallback data"
                : "Connecting to mock backend..."}
          </div>

          {/* ----------------------------------------------------------------
              Live conversation messages from the conversational agent.
              Rendered only after the conversation has been started so the
              demo messages below remain visible during development.
              ---------------------------------------------------------------- */}
          {convStarted && session?.messages.map((msg, i) => {
            if (msg.role === "user") {
              return (
                <UserMessage key={`live-${i}`} time={formatTime(msg.timestamp)}>
                  {msg.content}
                </UserMessage>
              )
            }

            return (
              <AgentMessage key={`live-${i}`} agent={msg.agentName ?? "Agent"} time={formatTime(msg.timestamp)}>
                {msg.content}
              </AgentMessage>
            )
          })}

          {/* Pending interrupt — renders specialised cards or falls back to text bubble */}
          {convStarted && !convLoading && session?.interrupt && (() => {
            const { type, message, questions, data, problemId, problemName, engine } = session.interrupt

            if (type === "sub_problem_confirmation") {
              return (
                <SystemCardSlot>
                  <DecomposerCard
                    cardData={data as DecomposerCardData}
                    onConfirm={() => handleInterruptAction({ confirmed: true })}
                    onAdjust={() => handleInterruptAction({ confirmed: false })}
                    loading={convLoading}
                  />
                </SystemCardSlot>
              )
            }

            if (type === "dataset_source_choice") {
              return (
                <SystemCardSlot>
                  <DataUploadCard
                    problemId={problemId ?? ""}
                    problemName={problemName ?? "Dataset"}
                    engine={(engine as "autogluon" | "autorag") ?? "autogluon"}
                    onUploadFile={(file) => handleChoiceAndUpload(file, problemId ?? "")}
                    onDiscover={() => handleInterruptAction({ choice: "discover" })}
                    onSkip={() => handleInterruptAction({ choice: "skip" })}
                    loading={convLoading}
                  />
                </SystemCardSlot>
              )
            }

            if (type === "awaiting_upload") {
              return (
                <SystemCardSlot>
                  <DataUploadCard
                    problemId={problemId ?? ""}
                    problemName={problemName ?? "Dataset"}
                    engine={(engine as "autogluon" | "autorag") ?? "autogluon"}
                    onUploadFile={(file) => handleFileUpload(problemId ?? "", file)}
                    onDiscover={() => handleInterruptAction({ choice: "discover" })}
                    onSkip={() => handleInterruptAction({ choice: "skip" })}
                    loading={convLoading}
                  />
                </SystemCardSlot>
              )
            }

            return (
              <AgentMessage agent="Agent" time={formatTime(new Date().toISOString())}>
                <span>{message}</span>
                {questions && questions.length > 0 && (
                  <ol className="mt-2 list-decimal pl-4 space-y-1">
                    {questions.map((q, qi) => (
                      <li key={qi}>{q}</li>
                    ))}
                  </ol>
                )}
              </AgentMessage>
            )
          })()}

          {/* Thinking indicator */}
          {convLoading && (
            <div className="flex gap-3">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-foreground text-background">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              </span>
              <div className="flex items-center rounded-2xl rounded-tl-sm border border-border bg-surface px-4 py-2.5 text-sm text-muted-foreground">
                Thinking…
              </div>
            </div>
          )}

          {/* Error banner */}
          {convError && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {convError}
            </div>
          )}

          {/* Completion banner — shown after final_review is confirmed and Redis is written */}
          {isComplete && (
            <div className="rounded-xl border border-border bg-surface px-4 py-4 text-center text-sm text-foreground">
              Experiment plan ready — session{" "}
              <span className="font-mono text-primary">{sessionId}</span> output written to Redis.
              Orchestrators can now consume it.
            </div>
          )}

          {/* ----------------------------------------------------------------
              Static demo messages — kept intact so the UI developer working
              on workspace/project management can reference the full flow.
              Hidden once the real conversation has started.
              ---------------------------------------------------------------- */}
          {!convStarted && (
            <>
              <UserMessage time="9:41 AM">
                We&apos;re losing enterprise customers and can&apos;t predict who&apos;s about to churn. Help me build
                something that flags at-risk accounts before renewal.
              </UserMessage>

              <AgentMessage agent="Intent Agent" time="9:41 AM">
                Got it. That&apos;s a <span className="font-medium text-foreground">churn prediction</span> problem. Before
                we touch data, let me translate this into a concrete ML strategy and lay out the path end-to-end. Here&apos;s
                what I&apos;m proposing.
              </AgentMessage>

              <SystemCardSlot>
                <StrategyCard strategy={workspace?.strategy} />
              </SystemCardSlot>

              <UserMessage time="9:43 AM">Looks right. The plan works for me &mdash; let&apos;s proceed.</UserMessage>

              <AgentMessage agent="Data Agent" time="9:43 AM">
                To train a reliable model I need historical account data. You can bring your own, connect a warehouse, or I
                can build a fresh labeled dataset from the open web using Exa. How do you want to source data?
              </AgentMessage>

              <SystemCardSlot>
                <DataSourceCard paths={workspace?.dataSources} />
              </SystemCardSlot>

              <UserMessage time="9:45 AM">
                We don&apos;t have clean historical labels. Build a dataset with Exa &mdash; B2B SaaS companies with firmographics
                and public churn signals.
              </UserMessage>

              <AgentMessage agent="Data Agent" time="9:45 AM">
                Understood. Synthesizing a labeled dataset is a billable, long-running job, so you&apos;ll approve scope and
                cost before anything runs. Configure the build below.
              </AgentMessage>

              <SystemCardSlot>
                <ExaBuilderCard run={workspace?.exaRun} />
              </SystemCardSlot>

              <AgentMessage agent="Data Agent" time="10:02 AM">
                Dataset ready &mdash; 4,820 rows across 14 features, fully traceable to source. Here&apos;s the final schema.
                Confirm it and I&apos;ll hand off to training. This is the last gate before model search begins.
              </AgentMessage>

              <SystemCardSlot>
                <SchemaConfirmCard dataset={assets?.dataset || workspace?.dataset} />
              </SystemCardSlot>

              <AgentMessage agent="Training Agent" time="10:04 AM">
                Schema locked. Running AutoGluon to search model families and ensembles against your churn label. No further
                input needed &mdash; I&apos;ll surface the leaderboard as it converges.
              </AgentMessage>

              <SystemCardSlot>
                <TrainingCard training={assets?.training || workspace?.training} />
              </SystemCardSlot>

              <AgentMessage agent="RAG Agent" time="10:19 AM">
                The strategy also called for a retrieval layer so account managers can ask questions in natural language. I
                built an AutoRAG pipeline over your dataset and source documents.
              </AgentMessage>

              <SystemCardSlot>
                <RagCard rag={workspace?.rag} />
              </SystemCardSlot>

              <AgentMessage agent="Deployment Agent" time="10:24 AM">
                Everything passed validation. I can promote the winning ensemble and the RAG endpoint to a managed,
                autoscaling deployment with a versioned API.
              </AgentMessage>

              <SystemCardSlot>
                <DeploymentCard />
              </SystemCardSlot>

              <AgentMessage agent="Billing Agent" time="10:24 AM">
                Promoting to production moves this workspace to metered usage. Review the cost summary and approve to go
                live.
              </AgentMessage>

              <SystemCardSlot>
                <BillingApprovalCard />
              </SystemCardSlot>
            </>
          )}

          <div className="h-2" ref={bottomRef} />
        </div>
      </div>

      <Composer
        onSubmit={handleSend}
        onFileSelect={handleComposerFile}
        disabled={convLoading || isComplete}
        placeholder={
          isComplete
            ? "Conversation complete."
            : session?.interrupt?.type === "clarification"
              ? "Type your answers here…"
              : "Describe a business problem, or ask the agent to source data…"
        }
      />
    </div>
  )
}

function EmptyWorkflowState({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="app-panel-raised w-full max-w-3xl rounded-[32px] p-8 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-error-soft text-primary shadow-sm">
          <Rocket className="h-7 w-7" aria-hidden="true" />
        </div>
        <h1 className="mt-5 font-heading text-4xl font-bold tracking-tight">{title}</h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted-foreground">{text}</p>
        <p className="mt-5 text-xs font-semibold text-primary">
          Use the sidebar actions to continue the setup flow.
        </p>
      </div>
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: ElementType
  label: string
  value: string
}) {
  return (
    <div className="app-control rounded-2xl p-3">
      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
      <div className="mt-3 truncate text-lg font-bold text-foreground">{value}</div>
      <div className="mt-0.5 truncate text-[11px] font-medium text-muted-foreground">{label}</div>
    </div>
  )
}
