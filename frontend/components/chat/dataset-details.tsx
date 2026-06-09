"use client"

import * as React from "react"
import { CalendarDays, Database, FileText, RefreshCw, Table2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchDatasets, type DatasetRecord, type Workspace } from "@/lib/api"
import { cn } from "@/lib/utils"

export function DatasetDetails({ selectedWorkspace }: { selectedWorkspace: Workspace | null }) {
  const [datasets, setDatasets] = React.useState<DatasetRecord[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const loadDatasets = React.useCallback(async () => {
    if (!selectedWorkspace) {
      setDatasets([])
      return
    }

    setLoading(true)
    setError(null)

    try {
      setDatasets(await fetchDatasets(selectedWorkspace.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load dataset details.")
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspace?.id])

  React.useEffect(() => {
    loadDatasets()
  }, [loadDatasets])

  const structuredCount = datasets.filter((dataset) => dataset.dataCategory === "structured").length
  const unstructuredCount = datasets.filter((dataset) => dataset.dataCategory === "unstructured").length

  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <section className="app-panel-raised rounded-[28px] p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-muted-foreground">Dataset storage</p>
              <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Datasets
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                {selectedWorkspace
                  ? `Dataset records for ${selectedWorkspace.name}, with S3 paths for CSV and PDF data.`
                  : "Select a workspace to view dataset records."}
              </p>
            </div>
            <Button
              variant="outline"
              onClick={loadDatasets}
              disabled={loading || !selectedWorkspace}
              className="rounded-full"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
              Refresh
            </Button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <SummaryStat icon={Database} label="Datasets" value={loading ? "..." : String(datasets.length)} />
            <SummaryStat icon={Table2} label="Structured CSV" value={loading ? "..." : String(structuredCount)} />
            <SummaryStat icon={FileText} label="Unstructured PDF" value={loading ? "..." : String(unstructuredCount)} />
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
            {error}
          </div>
        )}

        {!selectedWorkspace ? (
          <EmptyState title="No workspace selected" text="Open Workspaces and select one before viewing dataset details." />
        ) : loading ? (
          <div className="app-panel-raised rounded-[28px] p-6 text-sm text-muted-foreground">
            Loading dataset details...
          </div>
        ) : datasets.length === 0 ? (
          <EmptyState
            title="No datasets found"
            text="Dataset rows from Postgres will appear here after CSV or PDF data is registered with an S3 path."
          />
        ) : (
          <div className="grid gap-4">
            {datasets.map((dataset) => (
              <article key={dataset.id} className="app-panel-raised rounded-[28px] p-5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-heading text-2xl font-bold text-foreground">{dataset.name}</h2>
                      <span className="rounded-full bg-info-soft px-3 py-1 text-xs font-bold text-info">
                        {dataset.dataCategory || "unknown"}
                      </span>
                      <span className="rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success">
                        {dataset.dataFormat || "unknown"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm font-medium text-muted-foreground">
                      Project: {dataset.projectName}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-surface-muted px-3 py-1 text-xs font-bold text-muted-foreground">
                    {dataset.status}
                  </span>
                </div>

                <dl className="mt-5 grid gap-3 border-t border-border pt-4 md:grid-cols-2">
                  <Detail label="S3 path" value={dataset.s3Path || dataset.storageUri || "Not stored"} wide />
                  <Detail label="Source" value={dataset.sourceType} />
                  <Detail label="Rows" value={String(dataset.rowCount)} />
                  <Detail label="Columns" value={String(dataset.columnCount)} />
                  <Detail label="Quality" value={dataset.qualityScore == null ? "Not scored" : `${dataset.qualityScore}%`} />
                  <Detail label="Target" value={dataset.targetColumn || "None"} />
                  <Detail label="Task" value={dataset.taskType || "Unknown"} />
                  <Detail label="Created" value={formatDate(dataset.createdAt)} icon={CalendarDays} />
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

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "unknown"

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date)
}
