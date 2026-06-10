"use client"

import * as React from "react"
import { CalendarDays, Lightbulb, RefreshCw, Target, Workflow } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchUseCases, type UseCaseRecord, type Workspace } from "@/lib/api"
import { cn } from "@/lib/utils"

export function UseCaseDetails({ selectedWorkspace }: { selectedWorkspace: Workspace | null }) {
  const [useCases, setUseCases] = React.useState<UseCaseRecord[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const loadUseCases = React.useCallback(async () => {
    if (!selectedWorkspace) {
      setUseCases([])
      return
    }

    setLoading(true)
    setError(null)

    try {
      setUseCases(await fetchUseCases(selectedWorkspace.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load use-case details.")
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspace?.id])

  React.useEffect(() => {
    loadUseCases()
  }, [loadUseCases])

  const activeCount = useCases.filter((useCase) => useCase.status.toLowerCase() === "active").length
  const projectCount = new Set(useCases.map((useCase) => useCase.projectId)).size

  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <section className="app-panel-raised rounded-[28px] p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-muted-foreground">Use-case registry</p>
              <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Use Cases
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                {selectedWorkspace
                  ? `Use-case details for ${selectedWorkspace.name}, fetched asynchronously from Postgres.`
                  : "Select a workspace to view use-case records."}
              </p>
            </div>
            <Button
              variant="outline"
              onClick={loadUseCases}
              disabled={loading || !selectedWorkspace}
              className="rounded-full"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
              Refresh
            </Button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <SummaryStat icon={Lightbulb} label="Use cases" value={loading ? "..." : String(useCases.length)} />
            <SummaryStat icon={Workflow} label="Projects" value={loading ? "..." : String(projectCount)} />
            <SummaryStat icon={Target} label="Active" value={loading ? "..." : String(activeCount)} />
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
            {error}
          </div>
        )}

        {!selectedWorkspace ? (
          <EmptyState title="No workspace selected" text="Open Workspaces and select one before viewing use-case details." />
        ) : loading ? (
          <div className="app-panel-raised rounded-[28px] p-6 text-sm text-muted-foreground">
            Loading use-case details...
          </div>
        ) : useCases.length === 0 ? (
          <EmptyState
            title="No use cases found"
            text="Use cases generated from strategy approval or stored in Postgres will appear here."
          />
        ) : (
          <div className="grid gap-4">
            {useCases.map((useCase) => (
              <article key={useCase.id} className="app-panel-raised rounded-[28px] p-5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-heading text-2xl font-bold text-foreground">{useCase.name}</h2>
                      <span className="rounded-full bg-info-soft px-3 py-1 text-xs font-bold text-info">
                        {formatTaskType(useCase.taskType)}
                      </span>
                    </div>
                    <p className="mt-2 text-sm font-medium text-muted-foreground">
                      Project: {useCase.projectName}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-surface-muted px-3 py-1 text-xs font-bold text-muted-foreground">
                    {useCase.status}
                  </span>
                </div>

                <p className="mt-4 border-t border-border pt-4 text-sm leading-6 text-muted-foreground">
                  {useCase.businessProblem || useCase.description || "No business problem recorded."}
                </p>

                <dl className="mt-4 grid gap-3 md:grid-cols-2">
                  <Detail label="Use case ID" value={useCase.id} wide />
                  <Detail label="Project ID" value={useCase.projectId} wide />
                  <Detail label="Task type" value={useCase.taskType || "Unknown"} />
                  <Detail label="Created" value={formatDate(useCase.createdAt)} icon={CalendarDays} />
                  <Detail label="Updated" value={formatDate(useCase.updatedAt)} icon={CalendarDays} />
                </dl>

                {useCase.kpis.length > 0 && (
                  <div className="mt-4 rounded-2xl bg-surface-muted p-4">
                    <div className="text-xs font-bold uppercase tracking-wide text-muted-foreground">KPIs</div>
                    <ul className="mt-2 space-y-1 text-sm text-foreground">
                      {useCase.kpis.map((kpi, index) => (
                        <li key={index}>{formatKpi(kpi)}</li>
                      ))}
                    </ul>
                  </div>
                )}
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

function formatKpi(value: unknown): string {
  if (typeof value === "string") return value
  if (value && typeof value === "object") return JSON.stringify(value)
  return String(value)
}

function formatTaskType(value: string): string {
  if (!value) return "Unknown"
  return value.replaceAll("_", " ")
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
