"use client"

import * as React from "react"
import { CalendarDays, FolderKanban, Plus, RefreshCw, Target, Trash2, Workflow, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { createProject, deleteProject, fetchProjects, type Project, type Workspace } from "@/lib/api"
import { cn } from "@/lib/utils"

export function ProjectDetails({
  selectedWorkspace,
  selectedProject,
  onProjectChange,
  onProjectDeleted,
}: {
  selectedWorkspace: Workspace | null
  selectedProject: Project | null
  onProjectChange: (project: Project) => void
  onProjectDeleted?: (projectId: string) => void
}) {
  const [projects, setProjects] = React.useState<Project[]>([])
  const [loading, setLoading] = React.useState(false)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [creating, setCreating] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = React.useState<string | null>(null)
  const [deleting, setDeleting] = React.useState(false)

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

  async function handleDeleteProject(projectId: string) {
    setDeleting(true)
    setError(null)
    try {
      await deleteProject(projectId)
      setConfirmDeleteId(null)
      onProjectDeleted?.(projectId)
      await loadProjects()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete project.")
    } finally {
      setDeleting(false)
    }
  }

  async function handleCreateProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedWorkspace) return
    setCreating(true)
    setError(null)

    const formData = new FormData(event.currentTarget)
    try {
      const project = await createProject({
        name: String(formData.get("projectName") || ""),
        description: String(formData.get("projectDescription") || "") || undefined,
        workspaceId: selectedWorkspace.id,
      })
      onProjectChange(project)
      setCreateOpen(false)
      await loadProjects()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project.")
    } finally {
      setCreating(false)
    }
  }

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
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => setCreateOpen(true)}
                disabled={!selectedWorkspace}
                className="rounded-full"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                Create project
              </Button>
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

        {confirmDeleteId && (
          <div
            className="fixed inset-0 z-[130] flex items-center justify-center bg-[var(--overlay)] px-4 backdrop-blur-sm"
            role="dialog"
            aria-modal="true"
          >
            <div className="app-panel w-full max-w-sm rounded-[28px] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground">Delete project?</h2>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    This will permanently delete the project and all its data. This action cannot be undone.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setConfirmDeleteId(null)}
                  className="rounded-full p-2 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
                  aria-label="Close dialog"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmDeleteId(null)}
                  className="app-control inline-flex h-10 items-center justify-center rounded-full px-5 text-sm font-semibold text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={deleting}
                  onClick={() => handleDeleteProject(confirmDeleteId)}
                  className="app-accent-shadow inline-flex h-10 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}

        {createOpen && (
          <div
            className="fixed inset-0 z-[130] flex items-center justify-center bg-[var(--overlay)] px-4 backdrop-blur-sm"
            role="dialog"
            aria-modal="true"
          >
            <form onSubmit={handleCreateProject} className="app-panel w-full max-w-md rounded-[28px] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-heading text-2xl font-bold tracking-tight">Create project</h2>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    This project will be created inside <span className="font-semibold text-foreground">{selectedWorkspace?.name}</span>.
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
                <span className="text-sm font-medium text-foreground">Project name</span>
                <input
                  name="projectName"
                  required
                  minLength={2}
                  placeholder="Churn Prediction Model"
                  className="app-control mt-1.5 h-11 w-full rounded-full px-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                />
              </label>

              <label className="mt-4 block">
                <span className="text-sm font-medium text-foreground">Description <span className="text-muted-foreground">(optional)</span></span>
                <input
                  name="projectDescription"
                  placeholder="What is this project about?"
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
            <Button onClick={() => setCreateOpen(true)} className="mt-5 rounded-full">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Create project
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {projects.map((project) => (
              <div
                key={project.id}
                className={cn(
                  "app-panel-raised rounded-[28px] p-5 transition",
                  project.id === selectedProject?.id && "ring-2 ring-primary/45",
                )}
              >
                <button
                  type="button"
                  onClick={() => onProjectChange(project)}
                  className="w-full text-left"
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

                <div className="mt-4 flex justify-end border-t border-border pt-3">
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteId(project.id)}
                    className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold text-destructive hover:bg-destructive/10 transition"
                    aria-label={`Delete ${project.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Delete
                  </button>
                </div>
              </div>
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
