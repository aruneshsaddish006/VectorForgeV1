"use client"

import * as React from "react"
import { BrainCircuit, Clock, Database, RefreshCw, Trophy } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchModels, type ModelRecord, type Workspace } from "@/lib/api"
import { cn } from "@/lib/utils"

export function ModelDetails({ selectedWorkspace }: { selectedWorkspace: Workspace | null }) {
  const [models, setModels] = React.useState<ModelRecord[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const loadModels = React.useCallback(async () => {
    if (!selectedWorkspace) {
      setModels([])
      return
    }

    setLoading(true)
    setError(null)

    try {
      setModels(await fetchModels(selectedWorkspace.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load model details.")
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspace?.id])

  React.useEffect(() => {
    loadModels()
  }, [loadModels])

  const trainingRunCount = new Set(models.map((model) => model.trainingRunId)).size
  const bestModelCount = models.filter((model) => model.isBest).length
  const completedCount = new Set(
    models.filter((model) => model.trainingStatus === "complete").map((model) => model.trainingRunId),
  ).size

  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <section className="app-panel-raised rounded-[28px] p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-muted-foreground">Model registry</p>
              <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Models
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                {selectedWorkspace
                  ? `Trained model details for ${selectedWorkspace.name}, linked to use cases and datasets.`
                  : "Select a workspace to view trained model details."}
              </p>
            </div>
            <Button
              variant="outline"
              onClick={loadModels}
              disabled={loading || !selectedWorkspace}
              className="rounded-full"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
              Refresh
            </Button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <SummaryStat icon={BrainCircuit} label="Training runs" value={loading ? "..." : String(trainingRunCount)} />
            <SummaryStat icon={Trophy} label="Best models" value={loading ? "..." : String(bestModelCount)} />
            <SummaryStat icon={Clock} label="Completed" value={loading ? "..." : String(completedCount)} />
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
            {error}
          </div>
        )}

        {!selectedWorkspace ? (
          <EmptyState title="No workspace selected" text="Open Workspaces and select one before viewing trained models." />
        ) : loading ? (
          <div className="app-panel-raised rounded-[28px] p-6 text-sm text-muted-foreground">
            Loading model details...
          </div>
        ) : models.length === 0 ? (
          <EmptyState
            title="No models found"
            text="Training run and leaderboard rows from Postgres will appear here after a model is trained on a dataset."
          />
        ) : (
          <div className="grid gap-4">
            {models.map((model) => (
              <article
                key={`${model.trainingRunId}-${model.leaderboardEntryId || "run"}`}
                className={cn("app-panel-raised rounded-[28px] p-5", model.isBest && "ring-2 ring-primary/45")}
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-heading text-2xl font-bold text-foreground">
                        {model.modelName || model.predictorType}
                      </h2>
                      {model.isBest && (
                        <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-bold text-warning">
                          Best
                        </span>
                      )}
                      <span className="rounded-full bg-info-soft px-3 py-1 text-xs font-bold text-info">
                        {model.trainingStatus}
                      </span>
                    </div>
                    <p className="mt-2 text-sm font-medium text-muted-foreground">
                      {model.useCaseName} / {model.datasetName}
                    </p>
                  </div>
                  <div className="text-left sm:text-right">
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {model.bestMetricName || "Metric"}
                    </div>
                    <div className="font-heading text-2xl font-bold text-foreground">
                      {formatMetric(model.metricValue ?? model.bestMetricValue)}
                    </div>
                  </div>
                </div>

                <dl className="mt-5 grid gap-3 border-t border-border pt-4 md:grid-cols-2">
                  <Detail label="Project" value={model.projectName} />
                  <Detail label="Use case" value={`${model.useCaseName} (${model.useCaseTaskType})`} />
                  <Detail label="Dataset" value={model.datasetName} icon={Database} />
                  <Detail label="Dataset S3" value={model.datasetS3Path || "Not stored"} wide />
                  <Detail label="Model S3" value={model.artifactS3Path || "Not stored"} wide />
                  <Detail label="Engine" value={model.engine} />
                  <Detail label="Predictor" value={model.predictorType} />
                  <Detail label="Rank" value={model.rank == null ? "Run summary" : String(model.rank)} />
                  <Detail label="Latency" value={model.inferenceLatencyMs == null ? "Unknown" : `${model.inferenceLatencyMs} ms`} />
                  <Detail label="Train time" value={model.trainTimeSeconds == null ? "Unknown" : `${model.trainTimeSeconds}s`} />
                  <Detail label="Cost" value={model.computeCost == null ? "Unknown" : `$${model.computeCost.toFixed(4)}`} />
                  <Detail label="Created" value={formatDate(model.createdAt)} />
                  {model.sagemakerJobArn && <Detail label="SageMaker" value={model.sagemakerJobArn} wide />}
                  {model.errorMessage && <Detail label="Error" value={model.errorMessage} wide />}
                </dl>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="app-panel-raised rounded-[28px] p-8 text-center">
      <h2 className="font-heading text-2xl font-bold">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">{text}</p>
    </div>
  )
}

function SummaryStat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType
  label: string
  value: string
}) {
  return (
    <div className="app-control rounded-2xl p-4">
      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
      <div className="mt-3 truncate text-xl font-bold text-foreground">{value}</div>
      <div className="mt-0.5 text-xs font-medium text-muted-foreground">{label}</div>
    </div>
  )
}

function Detail({
  label,
  value,
  icon: Icon,
  wide = false,
}: {
  label: string
  value: string
  icon?: React.ElementType
  wide?: boolean
}) {
  return (
    <div className={cn("flex items-start gap-2 text-sm", wide && "md:col-span-2")}>
      {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
      <dt className="w-24 shrink-0 font-semibold text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-all font-medium text-foreground">{value}</dd>
    </div>
  )
}

function formatMetric(value?: number | null) {
  if (value == null) return "N/A"
  return value.toFixed(value >= 10 ? 2 : 4)
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "unknown"

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date)
}
