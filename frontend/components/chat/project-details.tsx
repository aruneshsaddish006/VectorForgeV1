"use client"

import * as React from "react"
import { CalendarDays, FolderKanban, RefreshCw, Target, Workflow } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchProjects, type Project, type Workspace } from "@/lib/api"
import { cn } from "@/lib/utils"

export function ProjectDetails({
  selectedWorkspace,
  selectedProject,
  onProjectChange,
}: {
  selectedWorkspace: Workspace | null
  selectedProject: Project | null
  onProjectChange: (project: Project) => void
}) {
  const [projects, setProjects] = React.useState<Project[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const loadProjects = React.useCallback(async () => {
    if (!selectedWorkspace) {
      setProjects([])
      return
    }

    setLoading(true)
    setError(null)

    try {
      const items = await fetchProjects(selectedWorkspace.id)
      setProjects(items)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load project details.")
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspace?.id])

  React.useEffect(() => {
    loadProjects()
  }, [loadProjects])

  const activeProject = projects.find((project) => project.id === selectedProject?.id)
  const activeCount = projects.filter((project) => project.status.toLowerCase() === "active").length

  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <section className="app-panel-raised rounded-[28px] p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-muted-foreground">Project registry</p>
              <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Projects
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                {selectedWorkspace
                  ? `Project details for ${selectedWorkspace.name}, fetched from the authenticated backend.`
                  : "Select a workspace to view its projects."}
              </p>
            </div>
            <Button
              variant="outline"
              onClick={loadProjects}
              disabled={loading || !selectedWorkspace}
              className="rounded-full"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
              Refresh
            </Button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <SummaryStat icon={FolderKanban} label="Projects" value={loading ? "..." : String(projects.length)} />
            <SummaryStat icon={Workflow} label="Active" value={loading ? "..." : String(activeCount)} />
            <SummaryStat icon={Target} label="Selected" value={activeProject?.name || "None"} />
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
            {error}
          </div>
        )}

        {!selectedWorkspace ? (
          <div className="app-panel-raised rounded-[28px] p-8 text-center">
            <h2 className="font-heading text-2xl font-bold">No workspace selected</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Open Workspaces and select one before viewing project-level details.
            </p>
          </div>
        ) : loading ? (
          <div className="app-panel-raised rounded-[28px] p-6 text-sm text-muted-foreground">
            Loading project details...
          </div>
        ) : projects.length === 0 ? (
          <div className="app-panel-raised rounded-[28px] p-8 text-center">
            <h2 className="font-heading text-2xl font-bold">No projects found</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Create a project in this workspace to see project-level details here.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {projects.map((project) => (
              <button
                key={project.id}
                onClick={() => onProjectChange(project)}
                className={cn(
                  "app-panel-raised rounded-[28px] p-5 text-left transition",
                  project.id === selectedProject?.id && "ring-2 ring-primary/45",
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="truncate font-heading text-2xl font-bold text-foreground">{project.name}</h2>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {project.description || "No description"}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success">
                    {project.status}
                  </span>
                </div>

                <dl className="mt-5 grid gap-3 border-t border-border pt-4">
                  <DetailRow label="Project ID" value={project.id} />
                  <DetailRow label="Workspace ID" value={project.workspaceId} />
                  <DetailRow label="Created" value={formatDate(project.createdAt)} icon={CalendarDays} />
                </dl>
              </button>
            ))}
          </div>
        )}
      </div>
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

function DetailRow({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon?: React.ElementType
}) {
  return (
    <div className="flex items-start gap-2 text-sm">
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
