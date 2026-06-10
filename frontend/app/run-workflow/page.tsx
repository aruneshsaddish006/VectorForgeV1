"use client"

import { useSearchParams, useRouter } from "next/navigation"
import { Suspense } from "react"
import {
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  PlayCircle,
  ArrowLeft,
  Database,
  Brain,
  BarChart3,
  Rocket,
} from "lucide-react"
import { cn } from "@/lib/utils"

type StepStatus = "complete" | "running" | "pending"

type WorkflowStep = {
  id: string
  label: string
  description: string
  icon: React.ElementType
  status: StepStatus
  duration?: string
}

const MOCK_STEPS: WorkflowStep[] = [
  {
    id: "data_validation",
    label: "Data validation",
    description: "Validating schema, null rates, and class balance from S3",
    icon: Database,
    status: "complete",
    duration: "12s",
  },
  {
    id: "feature_engineering",
    label: "Feature engineering",
    description: "AutoGluon preprocessing — encoding, imputation, scaling",
    icon: Brain,
    status: "running",
  },
  {
    id: "model_search",
    label: "Model search",
    description: "3 rounds × 3 experiments — LightGBM, XGBoost, CatBoost, NN",
    icon: BarChart3,
    status: "pending",
  },
  {
    id: "evaluation",
    label: "Evaluation & leaderboard",
    description: "ROC-AUC, F1, precision-recall across all candidates",
    icon: CheckCircle2,
    status: "pending",
  },
  {
    id: "deployment",
    label: "Deployment approval",
    description: "Human-in-the-loop gate before endpoint provisioning",
    icon: Rocket,
    status: "pending",
  },
]

function StatusIcon({ status }: { status: StepStatus }) {
  if (status === "complete")
    return <CheckCircle2 className="h-5 w-5 text-success" aria-label="Complete" />
  if (status === "running")
    return <Loader2 className="h-5 w-5 animate-spin text-primary" aria-label="Running" />
  return <Circle className="h-5 w-5 text-muted-foreground/40" aria-label="Pending" />
}

function StepRow({ step, index }: { step: WorkflowStep; index: number }) {
  const Icon = step.icon
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            step.status === "complete" && "bg-success-soft text-success",
            step.status === "running" && "bg-info-soft text-primary",
            step.status === "pending" && "bg-surface-muted text-muted-foreground",
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        {index < MOCK_STEPS.length - 1 && (
          <div
            className={cn("mt-1 w-px flex-1", step.status === "complete" ? "bg-success/30" : "bg-border")}
          />
        )}
      </div>
      <div className="min-w-0 pb-6">
        <div className="flex items-center gap-2">
          <StatusIcon status={step.status} />
          <span
            className={cn(
              "text-sm font-semibold",
              step.status === "pending" ? "text-muted-foreground" : "text-foreground",
            )}
          >
            {step.label}
          </span>
          {step.duration && (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <Clock className="h-3 w-3" aria-hidden="true" />
              {step.duration}
            </span>
          )}
          {step.status === "running" && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
              Running
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{step.description}</p>
      </div>
    </div>
  )
}

function RunWorkflowContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const sessionId = searchParams.get("session") ?? "unknown"
  const runningStep = MOCK_STEPS.find((s) => s.status === "running")

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-canvas p-3 text-foreground sm:p-4">
      <div className="flex min-h-0 flex-1 items-start justify-center overflow-y-auto py-8">
        <div className="w-full max-w-2xl space-y-6 px-4">

          {/* Header */}
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
              <div>
                <h1 className="text-xl font-bold text-foreground">Workflow running</h1>
                <p className="text-sm text-muted-foreground">
                  {runningStep ? `Currently: ${runningStep.label}` : "Queued for execution"}
                </p>
              </div>
            </div>
          </div>

          {/* Session */}
          <div className="rounded-xl border border-border bg-surface px-4 py-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Session ID</p>
            <p className="mt-0.5 break-all font-mono text-xs text-foreground">{sessionId}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Redis key: <span className="font-mono">vforge:conv:{sessionId}</span>
            </p>
          </div>

          {/* Pipeline steps */}
          <div className="rounded-xl border border-border bg-surface px-5 py-5">
            <p className="mb-4 text-sm font-semibold text-foreground">Execution pipeline</p>
            {MOCK_STEPS.map((step, i) => (
              <StepRow key={step.id} step={step} index={i} />
            ))}
          </div>

          {/* Live log */}
          <div className="rounded-xl border border-border bg-surface">
            <div className="border-b border-border px-4 py-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Live log</p>
            </div>
            <div className="space-y-1 px-4 py-3 font-mono text-[11px] text-muted-foreground">
              <p><span className="text-success">✓</span> Loaded dataset from S3 — 10,000 rows × 18 cols</p>
              <p><span className="text-success">✓</span> Schema validated — target: Churn (binary, 18.4% positive rate)</p>
              <p><span className="text-primary">→</span> AutoGluon preprocessing pipeline started…</p>
              <p className="pl-4 opacity-60">Fitting label encoder on categorical features</p>
              <p className="pl-4 opacity-60">Imputing 3 columns with median strategy</p>
              <p className="flex items-center gap-1.5">
                <Loader2 className="h-3 w-3 animate-spin text-primary" aria-hidden="true" />
                <span className="text-primary">Feature matrix ready — awaiting model search queue</span>
              </p>
            </div>
          </div>

          <p className="text-center text-xs text-muted-foreground">
            Preview only — connect the orchestrator to replace with live AutoGluon run data.
          </p>
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
