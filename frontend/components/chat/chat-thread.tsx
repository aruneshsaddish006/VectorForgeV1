"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2, MessageSquareText, Rocket } from "lucide-react"
import { UserMessage, AgentMessage, SystemCardSlot } from "./messages"
import { Composer } from "./composer"
import { DecomposerCard, type DecomposerCardData } from "@/components/cards/decomposer-card"
import { DataUploadCard } from "@/components/cards/data-upload-card"
import {
  fetchUseCases,
  getConversationState,
  persistStrategyUseCases,
  respondToInterrupt,
  streamRespondToInterrupt,
  streamStartConversation,
  uploadDataset,
  type ConversationStreamProgress,
  type ConversationStreamTokenMeta,
  type PersistStrategyUseCase,
  type Project,
  type UseCaseRecord,
  type Workspace,
} from "@/lib/api"
import type { ConversationMessage, ConversationSession } from "@/lib/types"

// ---------------------------------------------------------------------------
// Session ID helpers
// ---------------------------------------------------------------------------

const DEFAULT_WORKSPACE_ID = "default_workspace"
const DEFAULT_USE_CASE_ID = "default_use_case"

type StreamingAgentMessage = {
  content: string
  agentName: string | null
  timestamp: string
}

/**
 * Deterministic session ID scoped to a specific user + workspace + project.
 * Falls back to default IDs so a session can always be created, even before
 * workspace/project management has been set up by the other developer.
 */
function buildSessionId(
  userId: string,
  workspaceId: string,
  useCaseId: string,
): string {
  return `${userId}_${workspaceId}_${useCaseId}`
}

function uniqueSessionIds(ids: string[]): string[] {
  return Array.from(new Set(ids.filter(Boolean)))
}

function buildSessionCandidates({
  userId,
  workspaceId,
  projectId,
  useCaseId,
}: {
  userId: string
  workspaceId: string
  projectId?: string | null
  useCaseId?: string | null
}): string[] {
  return uniqueSessionIds([
    buildSessionId(userId, workspaceId, useCaseId || projectId || DEFAULT_USE_CASE_ID),
    projectId ? buildSessionId(userId, workspaceId, projectId) : "",
    buildSessionId(userId, workspaceId, DEFAULT_USE_CASE_ID),
  ])
}

function messageKey(message: ConversationMessage): string {
  return [
    message.role,
    message.agentName ?? "",
    message.timestamp ?? "",
    message.cardType ?? "",
    message.content,
  ].join("::")
}

function mergeMessages(
  existing: ConversationMessage[] = [],
  incoming: ConversationMessage[] = [],
): ConversationMessage[] {
  const seen = new Set<string>()
  const merged: ConversationMessage[] = []

  for (const message of [...existing, ...incoming]) {
    const key = messageKey(message)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(message)
  }

  return merged
}

function appendMessage(
  session: ConversationSession | null,
  message: ConversationMessage,
  fallbackSessionId?: string | null,
): ConversationSession | null {
  if (!session) {
    if (!fallbackSessionId) return null
    return {
      sessionId: fallbackSessionId,
      status: "intake",
      messages: [message],
      interrupt: null,
    }
  }

  return {
    ...session,
    messages: mergeMessages(session.messages, [message]),
  }
}

/** Merge server snapshot into client session.
 *  The server snapshot is authoritative for status/interrupt.
 *  Messages are unioned because streamed messages may reach the UI before the
 *  final checkpoint snapshot is fully available. */
function mergeSession(
  prev: ConversationSession | null,
  updated: ConversationSession,
): ConversationSession {
  return {
    ...updated,
    messages: mergeMessages(prev?.messages ?? [], updated.messages ?? []),
  }
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

function getStoredUserName(): string {
  if (typeof window === "undefined") return ""
  try {
    const raw = window.localStorage.getItem("forge_ai_user")
    const user = raw ? JSON.parse(raw) : null
    return user?.fullName || user?.email || ""
  } catch {
    return ""
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch {
    return ""
  }
}

function strategyToPersistedUseCases(cardData: DecomposerCardData): PersistStrategyUseCase[] {
  return (cardData.ml_problems || []).map((problem) => ({
    name: problem.name,
    taskType: problem.autogluon_task_type || problem.autorag_task_type || problem.engine || "unknown",
    businessProblem:
      cardData.constraint_summary?.narrative ||
      `Generated ${problem.engine === "autorag" ? "retrieval" : "machine learning"} use case: ${problem.name}`,
    kpis: (problem.business_kpis || []).map(String),
  }))
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
  const [useCases, setUseCases] = useState<UseCaseRecord[]>([])
  const [confirmedStrategy, setConfirmedStrategy] = useState<DecomposerCardData | null>(null)
  const [strategyConfirmed, setStrategyConfirmed] = useState(false)

  // Conversational agent state
  const [session, setSession] = useState<ConversationSession | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [convStarted, setConvStarted] = useState(false)
  const [convLoading, setConvLoading] = useState(false)
  const [convHydrating, setConvHydrating] = useState(false)
  const [convError, setConvError] = useState<string | null>(null)
  const [streamingAgent, setStreamingAgent] = useState<StreamingAgentMessage | null>(null)
  const [streamProgress, setStreamProgress] = useState<ConversationStreamProgress | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!selectedWorkspace || !selectedProject) {
      setUseCases([])
      return
    }
    fetchUseCases(selectedWorkspace.id, selectedProject.id)
      .then(setUseCases)
      .catch(() => setUseCases([]))
  }, [selectedWorkspace?.id, selectedProject?.id])

  const selectedUseCase = useCases[0] ?? null

  // Build deterministic session ID on every workspace/use-case change.
  // This is the persistence key used by the conversational service checkpoint.
  useEffect(() => {
    if (!selectedWorkspace || !selectedProject) {
      setSessionId(null)
      setSession(null)
      setConvStarted(false)
      setConvHydrating(false)
      setConvLoading(false)
      return
    }

    let cancelled = false
    const userId = getStoredUserId()
    const wsId = selectedWorkspace.id ?? DEFAULT_WORKSPACE_ID
    const candidates = buildSessionCandidates({
      userId,
      workspaceId: wsId,
      projectId: selectedProject.id,
      useCaseId: selectedUseCase?.id,
    })
    const primarySessionId = candidates[0]

    setSessionId(primarySessionId)
    setSession(null)
    setConvStarted(false)
    setConfirmedStrategy(null)
    setStrategyConfirmed(false)
    setStreamingAgent(null)
    setStreamProgress(null)
    setConvError(null)

    async function hydrateConversation() {
      setConvHydrating(true)
      setConvLoading(true)

      for (const candidate of candidates) {
        try {
          const hydrated = await getConversationState(candidate)
          if (cancelled) return
          setSessionId(hydrated.sessionId || candidate)
          setSession(hydrated)
          setConvStarted(hydrated.messages.length > 0 || Boolean(hydrated.interrupt))
          return
        } catch {
          // Try the next candidate. This covers new use-case scoped sessions,
          // older project-scoped sessions, and empty workspaces without history.
        }
      }

      if (!cancelled) {
        setSession(null)
        setConvStarted(false)
        setSessionId(primarySessionId)
      }
    }

    hydrateConversation().finally(() => {
      if (!cancelled) {
        setConvHydrating(false)
        setConvLoading(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [selectedWorkspace?.id, selectedProject?.id, selectedUseCase?.id])

  useEffect(() => {
    if (!session) return

    if (session.interrupt?.type === "sub_problem_confirmation" && session.interrupt.data) {
      setConfirmedStrategy(session.interrupt.data as DecomposerCardData)
      setStrategyConfirmed(false)
      return
    }

    const strategyMessage = [...session.messages]
      .reverse()
      .find((message) => message.cardType === "strategy" && message.cardData)

    if (strategyMessage?.cardData) {
      setConfirmedStrategy(strategyMessage.cardData as DecomposerCardData)
      setStrategyConfirmed(true)
    }
  }, [session])

  // Auto-scroll when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [session?.messages.length])

  async function handleSend(text: string) {
    if (!sessionId || convLoading) return
    setConvError(null)
    setConvLoading(true)
    setStreamingAgent(null)
    setStreamProgress(null)

    let shouldStartConversation = !convStarted
    if (shouldStartConversation) {
      try {
        const hydrated = await getConversationState(sessionId)
        if (hydrated.messages.length > 0 || hydrated.interrupt) {
          setSession(hydrated)
          setConvStarted(true)
          shouldStartConversation = false
        }
      } catch {
        shouldStartConversation = true
      }
    }

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
    setConvStarted(true)

    try {
      if (shouldStartConversation) {
        await new Promise<void>((resolve, reject) => {
          streamStartConversation(sessionId, text, {
            ...streamHandlers(resolve, reject),
          })
        })
      } else {
        await new Promise<void>((resolve, reject) => {
          streamRespondToInterrupt(sessionId, { answers: { "0": text } }, {
            ...streamHandlers(resolve, reject),
          })
        })
      }
    } catch (err) {
      setConvError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setConvLoading(false)
    }
  }

  function streamHandlers(resolve: () => void, reject: (error: Error) => void) {
    return {
      onMessage(msg: ConversationMessage) {
        setSession((prev) => appendMessage(prev, msg, sessionId))
      },
      onTokenStart(meta: ConversationStreamTokenMeta) {
        setStreamProgress(null)
        setStreamingAgent({
          content: "",
          agentName: meta.agentName,
          timestamp: meta.timestamp || new Date().toISOString(),
        })
      },
      onToken(token: string, meta: ConversationStreamTokenMeta) {
        setStreamProgress(null)
        setStreamingAgent((prev) => ({
          content: `${prev?.content ?? ""}${token}`,
          agentName: prev?.agentName ?? meta.agentName,
          timestamp: prev?.timestamp ?? meta.timestamp ?? new Date().toISOString(),
        }))
      },
      onTokenEnd(msg: ConversationMessage) {
        setSession((prev) => appendMessage(prev, msg, sessionId))
        setStreamingAgent(null)
      },
      onProgress(progress: ConversationStreamProgress) {
        setStreamProgress(progress)
      },
      onComplete(updated: ConversationSession) {
        setConvStarted(true)
        setStreamingAgent(null)
        setStreamProgress(null)
        setSession((prev) => mergeSession(prev, updated))
        resolve()
      },
      onError(detail: string) {
        setStreamingAgent(null)
        reject(new Error(detail))
      },
    }
  }

  async function handleInterruptAction(payload: Record<string, unknown>) {
    if (!sessionId || convLoading) return
    setConvError(null)
    setConvLoading(true)
    setStreamingAgent(null)
    setStreamProgress(null)
    if (
      payload.confirmed === true &&
      session?.interrupt?.type === "sub_problem_confirmation" &&
      session.interrupt.data
    ) {
      const strategyData = session.interrupt.data as DecomposerCardData
      setConfirmedStrategy(strategyData)
      setStrategyConfirmed(true)
      setSession((prev) => (prev ? { ...prev, interrupt: null } : prev))
      if (selectedWorkspace && selectedProject) {
        const useCasesToPersist = strategyToPersistedUseCases(strategyData)
        if (useCasesToPersist.length > 0) {
          try {
            await persistStrategyUseCases({
              workspaceId: selectedWorkspace.id,
              projectId: selectedProject.id,
              useCases: useCasesToPersist,
            })
            fetchUseCases(selectedWorkspace.id, selectedProject.id)
              .then(setUseCases)
              .catch(() => undefined)
          } catch (err) {
            setConvError(
              err instanceof Error
                ? `Strategy confirmed, but use cases were not saved to Postgres: ${err.message}`
                : "Strategy confirmed, but use cases were not saved to Postgres.",
            )
          }
        }
      }
    }
    try {
      await new Promise<void>((resolve, reject) => {
        streamRespondToInterrupt(sessionId, payload, {
          ...streamHandlers(resolve, reject),
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
  const userName = getStoredUserName()
  const heroTitle = selectedUseCase?.name || selectedProject.name
  const heroDescription =
    selectedUseCase?.description ||
    selectedProject.description ||
    `${selectedWorkspace.name} brings data sourcing, model search, retrieval, approvals, and deployment into one guided AI product workflow.`

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <section className="app-panel-raised overflow-hidden rounded-[28px] p-6 sm:p-8">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-muted-foreground">
                {userName ? `Welcome back, ${userName}` : "Welcome back"}
              </p>
              <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                {heroTitle}
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                {heroDescription}
              </p>
            </div>
          </section>

          <div className="flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Today &middot; {heroTitle}
            </span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <div className="app-control mx-auto rounded-full px-4 py-1.5 text-[11px] font-semibold text-muted-foreground">
            {selectedWorkspace.name} / {selectedProject.name}
            {selectedUseCase ? ` / ${selectedUseCase.name}` : ""}
          </div>

          {/* ----------------------------------------------------------------
              Persisted conversation messages from the conversational agent.
              Hydrated by deterministic user + workspace + use-case session ID.
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

          {streamingAgent && (
            <AgentMessage
              agent={streamingAgent.agentName ?? "Agent"}
              time={formatTime(streamingAgent.timestamp)}
            >
              {streamingAgent.content}
              <span className="ml-0.5 inline-block h-4 w-1 translate-y-0.5 animate-pulse rounded-full bg-primary" />
            </AgentMessage>
          )}

          {streamProgress && (
            <SystemCardSlot>
              <StrategyProgress progress={streamProgress} />
            </SystemCardSlot>
          )}

          {convStarted &&
            confirmedStrategy &&
            (strategyConfirmed || session?.interrupt?.type !== "sub_problem_confirmation") && (
            <SystemCardSlot>
              <DecomposerCard cardData={confirmedStrategy} confirmed />
            </SystemCardSlot>
          )}

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
          {convLoading && !streamingAgent && !streamProgress && (
            <div className="flex gap-3">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-foreground text-background">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              </span>
              <div className="flex items-center rounded-2xl rounded-tl-sm border border-border bg-surface px-4 py-2.5 text-sm text-muted-foreground">
                {convHydrating ? "Loading previous conversation..." : "Thinking..."}
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

          {!convStarted && !convLoading && (
            <EmptyBuildAIState
              useCaseName={heroTitle}
              description={heroDescription}
            />
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

function EmptyBuildAIState({
  useCaseName,
  description,
}: {
  useCaseName: string
  description: string
}) {
  return (
    <div className="app-panel-raised mx-auto max-w-3xl rounded-[28px] p-6 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-info-soft text-primary">
        <MessageSquareText className="h-6 w-6" aria-hidden="true" />
      </div>
      <h2 className="mt-4 font-heading text-2xl font-bold tracking-tight text-foreground">
        Build AI for {useCaseName}
      </h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
        {description}
      </p>
      <p className="mx-auto mt-4 max-w-lg text-xs font-medium leading-5 text-muted-foreground">
        Start the conversation below. Previous messages for this user, workspace, and use case will appear here automatically.
      </p>
    </div>
  )
}

function StrategyProgress({ progress }: { progress: ConversationStreamProgress }) {
  return (
    <div className="app-panel-raised rounded-[24px] border border-primary/20 p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-info-soft text-primary">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-bold text-foreground">{progress.label}</div>
          {progress.detail && (
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{progress.detail}</p>
          )}
        </div>
      </div>
    </div>
  )
}
