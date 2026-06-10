"use client"

import { CheckCircle2, RefreshCw, Database, Brain, FileText, ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import * as React from "react"

type TargetColumn = {
  inferred_name?: string
  type?: string
  reason?: string
}

type DatasetSource = {
  s3_path?: string
  row_count?: number | null
  dataset_url?: string
}

type MLProblemDataset = {
  description?: string
  target_column?: TargetColumn
  source?: DatasetSource
}

type MLProblem = {
  id: string
  name: string
  description?: string
  category?: string
  engine?: string
  autogluon_task_type?: string | null
  hypothesis_evidence?: string[]
  business_kpis?: string[]
  dataset?: MLProblemDataset
}

export type FinalOutput = {
  business_problem?: string
  domain?: string
  constraint_summary?: string
  ml_problems?: MLProblem[]
  session_cost_usd?: number
  ready_for_experiments?: boolean
  max_experiment_per_round?: number
  num_round?: number
}

const ENGINE_LABELS: Record<string, string> = {
  autogluon: "AutoGluon · Predictive",
  autorag: "AutoRAG · GenAI",
}

const ENGINE_COLORS: Record<string, string> = {
  autogluon: "bg-info-soft text-primary",
  autorag: "bg-warning-soft text-warning",
}

function ProblemCard({ problem }: { problem: MLProblem }) {
  const [expanded, setExpanded] = React.useState(false)
  const engine = problem.engine ?? "autogluon"
  const Icon = engine === "autorag" ? FileText : Brain
  const s3Path = problem.dataset?.source?.s3_path

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-start gap-3 p-4">
        <span
          className={cn(
            "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
            ENGINE_COLORS[engine] ?? "bg-surface-muted text-primary",
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-foreground">{problem.name}</h4>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                ENGINE_COLORS[engine] ?? "bg-surface-muted text-muted-foreground",
              )}
            >
              {ENGINE_LABELS[engine] ?? engine}
            </span>
            {problem.autogluon_task_type && (
              <span className="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                {problem.autogluon_task_type}
              </span>
            )}
          </div>

          {problem.description && (
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{problem.description}</p>
          )}

          {s3Path && (
            <div className="mt-2 flex items-center gap-1.5 rounded-lg border border-border bg-surface-muted px-2.5 py-1.5">
              <Database className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-foreground">{s3Path}</span>
            </div>
          )}

          {problem.dataset?.target_column?.inferred_name && (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              Target:{" "}
              <span className="font-mono text-foreground">
                {problem.dataset.target_column.inferred_name}
              </span>
              {problem.dataset.target_column.type && (
                <>
                  {" · "}
                  <span className="text-primary">{problem.dataset.target_column.type}</span>
                </>
              )}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 text-muted-foreground hover:text-foreground"
          aria-label={expanded ? "Collapse details" : "Expand details"}
        >
          {expanded
            ? <ChevronUp className="h-4 w-4" aria-hidden="true" />
            : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>

      {expanded && (
        <div className="space-y-3 border-t border-border px-4 pb-4 pt-3">
          {(problem.business_kpis ?? []).length > 0 && (
            <div>
              <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Business KPIs
              </p>
              <ul className="space-y-1">
                {problem.business_kpis!.map((kpi, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-foreground">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                    {kpi}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(problem.hypothesis_evidence ?? []).length > 0 && (
            <div>
              <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Evidence
              </p>
              <ul className="space-y-1">
                {problem.hypothesis_evidence!.map((ev, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
                    {ev}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {problem.dataset?.description && (
            <div>
              <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Dataset
              </p>
              <p className="text-xs text-muted-foreground">{problem.dataset.description}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function UsecasePlanCard({
  finalOutput,
  onConfirm,
  onRegenerate,
  loading = false,
}: {
  finalOutput?: FinalOutput | null
  onConfirm?: () => void
  onRegenerate?: () => void
  loading?: boolean
}) {
  const problems = finalOutput?.ml_problems ?? []
  const numRounds = finalOutput?.num_round ?? 3
  const maxPerRound = finalOutput?.max_experiment_per_round ?? 3

  return (
    <div className="w-full overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
      <header className="border-b border-border bg-surface-muted px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
          <h3 className="text-[15px] font-semibold text-foreground">
            Experiment plan — {problems.length} ML problem{problems.length !== 1 ? "s" : ""}
          </h3>
        </div>
        {finalOutput?.business_problem && (
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {finalOutput.business_problem}
          </p>
        )}
      </header>

      <div className="space-y-3 px-4 py-4 sm:px-5">
        {problems.map((prob) => (
          <ProblemCard key={prob.id} problem={prob} />
        ))}

        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface-muted px-3 py-2 text-[11px] text-muted-foreground">
          <span>
            <span className="font-medium text-foreground">{numRounds}</span> rounds ·{" "}
            <span className="font-medium text-foreground">{maxPerRound}</span> experiments/round
          </span>
          {(finalOutput?.session_cost_usd ?? 0) > 0 && (
            <span>
              Session cost:{" "}
              <span className="font-medium text-foreground">
                ${(finalOutput!.session_cost_usd!).toFixed(2)}
              </span>
            </span>
          )}
          {finalOutput?.domain && (
            <span className="capitalize">
              Domain:{" "}
              <span className="font-medium text-foreground">{finalOutput.domain}</span>
            </span>
          )}
        </div>

        {finalOutput?.constraint_summary && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {finalOutput.constraint_summary}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <Button onClick={onConfirm} disabled={loading}>
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            Confirm and start experiments
          </Button>
          <Button variant="outline" onClick={onRegenerate} disabled={loading}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Regenerate plan
          </Button>
        </div>
      </div>
    </div>
  )
}
