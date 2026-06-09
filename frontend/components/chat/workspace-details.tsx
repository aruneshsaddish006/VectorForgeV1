"use client"

import * as React from "react"
import { CalendarDays, Database, FolderKanban, Layers3, Plus, RefreshCw, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  createWorkspace,
  fetchProjects,
  fetchWorkspaces,
  persistWorkspace,
  type Project,
  type Workspace,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type WorkspaceWithProjects = {
  workspace: Workspace
  projects: Project[]
}

export function WorkspaceDetails({
  selectedWorkspace,
  onWorkspaceChange,
  onProjectChange,
}: {
  selectedWorkspace: Workspace | null
  onWorkspaceChange: (workspace: Workspace) => void
  onProjectChange: (project: Project) => void
}) {
  const [items, setItems] = React.useState<WorkspaceWithProjects[]>([])
  const [createOpen, setCreateOpen] = React.useState(false)
  const [loading, setLoading] = React.useState(true)
  const [creating, setCreating] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const loadWorkspaceDetails = React.useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const workspaces = await fetchWorkspaces()
      const details = await Promise.all(
        workspaces.map(async (workspace) => ({
          workspace,
          projects: await fetchProjects(workspace.id),
        })),
      )
      setItems(details)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load workspace details.")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadWorkspaceDetails()
  }, [loadWorkspaceDetails])

  async function handleCreateWorkspace(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreating(true)
    setError(null)

    const formData = new FormData(event.currentTarget)

    try {
      const workspace = await createWorkspace({
        name: String(formData.get("workspaceName") || ""),
      })
      onWorkspaceChange(workspace)
      persistWorkspace(workspace)
      setCreateOpen(false)
      await loadWorkspaceDetails()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create workspace.")
    } finally {
      setCreating(false)
    }
  }

  const projectCount = items.reduce((total, item) => total + item.projects.length, 0)
  const activeItem = items.find((item) => item.workspace.id === selectedWorkspace?.id)

  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <section className="app-panel-raised rounded-[28px] p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-muted-foreground">Workspace intelligence</p>
              <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Workspaces
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                Live workspace and project details fetched from the authenticated backend.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setCreateOpen(true)} className="rounded-full">
                <Plus className="h-4 w-4" aria-hidden="true" />
                Create workspace
              </Button>
              <Button variant="outline" onClick={loadWorkspaceDetails} disabled={loading} className="rounded-full">
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
                Refresh
              </Button>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <SummaryStat icon={Layers3} label="Workspaces" value={loading ? "..." : String(items.length)} />
            <SummaryStat icon={FolderKanban} label="Projects" value={loading ? "..." : String(projectCount)} />
            <SummaryStat icon={Database} label="Active" value={activeItem?.workspace.name || "None"} />
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
            {error}
          </div>
        )}

        {createOpen && (
          <div className="fixed inset-0 z-[130] flex items-center justify-center bg-[var(--overlay)] px-4 backdrop-blur-sm" role="dialog" aria-modal="true">
            <form onSubmit={handleCreateWorkspace} className="app-panel w-full max-w-md rounded-[28px] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-heading text-2xl font-bold tracking-tight">Create workspace</h2>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    This workspace will be stored in the database and mapped to your user account.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="rounded-full p-2 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
                  aria-label="Close dialog"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>

              <label className="mt-5 block">
                <span className="text-sm font-medium text-foreground">Workspace name</span>
                <input
                  name="workspaceName"
                  required
                  minLength={2}
                  placeholder="Acme AI Lab"
                  className="app-control mt-1.5 h-11 w-full rounded-full px-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                />
              </label>

              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="app-control inline-flex h-10 items-center justify-center rounded-full px-5 text-sm font-semibold text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="app-accent-shadow inline-flex h-10 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary-dark disabled:opacity-50"
                >
                  {creating ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        )}

        {loading ? (
          <div className="app-panel-raised rounded-[28px] p-6 text-sm text-muted-foreground">
            Loading workspace details...
          </div>
        ) : items.length === 0 ? (
          <div className="app-panel-raised rounded-[28px] p-8 text-center">
            <h2 className="font-heading text-2xl font-bold">No workspaces found</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Create a workspace to start organizing AI projects.
            </p>
            <Button onClick={() => setCreateOpen(true)} className="mt-5 rounded-full">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Create workspace
            </Button>
          </div>
        ) : (
          <div className="grid gap-4">
            {items.map(({ workspace, projects }) => (
              <article
                key={workspace.id}
                className={cn(
                  "app-panel-raised rounded-[28px] p-5 transition",
                  workspace.id === selectedWorkspace?.id && "ring-2 ring-primary/45",
                )}
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <button
                    onClick={() => {
                      onWorkspaceChange(workspace)
                      persistWorkspace(workspace)
                    }}
                    className="min-w-0 text-left"
                  >
                    <div className="flex items-center gap-3">
                      <span className="app-accent-shadow flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary text-lg font-bold text-primary-foreground">
                        {workspace.name.charAt(0).toUpperCase()}
                      </span>
                      <div className="min-w-0">
                        <h2 className="truncate font-heading text-2xl font-bold text-foreground">{workspace.name}</h2>
                        <p className="text-sm font-medium text-muted-foreground">{workspace.plan}</p>
                      </div>
                    </div>
                  </button>

                  <div className="rounded-full bg-info-soft px-3 py-1 text-xs font-bold text-info">
                    {projects.length} {projects.length === 1 ? "project" : "projects"}
                  </div>
                </div>

                <div className="mt-5 border-t border-border pt-4">
                  {projects.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No projects created in this workspace yet.</p>
                  ) : (
                    <div className="grid gap-3 md:grid-cols-2">
                      {projects.map((project) => (
                        <button
                          key={project.id}
                          onClick={() => {
                            onWorkspaceChange(workspace)
                            persistWorkspace(workspace)
                            onProjectChange(project)
                          }}
                          className="app-control rounded-2xl p-4 text-left"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <h3 className="truncate text-base font-bold text-foreground">{project.name}</h3>
                              <p className="mt-1 text-sm leading-5 text-muted-foreground">
                                {project.description || "No description"}
                              </p>
                            </div>
                            <span className="shrink-0 rounded-full bg-success-soft px-2.5 py-1 text-[11px] font-bold text-success">
                              {project.status}
                            </span>
                          </div>
                          <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                            <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
                            Created {formatDate(project.createdAt)}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </article>
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

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "unknown"

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date)
}
