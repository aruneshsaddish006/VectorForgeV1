"use client"

import * as React from "react"
import {
  Activity,
  CloudCog,
  Cpu,
  CreditCard,
  Database,
  FolderKanban,
  LayoutGrid,
  Lightbulb,
  MessageSquare,
  Network,
  Plus,
  Settings,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  createProject,
  createWorkspace,
  fetchProjects,
  fetchWorkspaces,
  persistWorkspace,
  type Project,
  type Workspace,
} from "@/lib/api"

type NavItem = {
  id: string
  label: string
  icon: React.ElementType
}

const PRIMARY_NAV: NavItem[] = [
  { id: "workspaces", label: "Workspaces", icon: LayoutGrid },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "datasets", label: "Datasets", icon: Database },
  { id: "models", label: "Models", icon: Cpu },
  { id: "use-cases", label: "Use Cases", icon: Lightbulb },
  { id: "rag", label: "RAG Pipelines", icon: Network },
  { id: "chat", label: "Build AI", icon: MessageSquare },
  { id: "deployments", label: "Deployments", icon: CloudCog },
]

const SECONDARY_NAV: NavItem[] = [
  { id: "activity", label: "Activity Log", icon: Activity },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "settings", label: "Settings", icon: Settings },
]

export function Sidebar({
  selectedWorkspace,
  selectedProject,
  activeView,
  onWorkspaceChange,
  onProjectChange,
  onViewChange,
}: {
  selectedWorkspace: Workspace | null
  selectedProject: Project | null
  activeView: string
  onWorkspaceChange: (workspace: Workspace) => void
  onProjectChange: (project: Project) => void
  onViewChange: (view: string) => void
}) {
  const [workspaces, setWorkspaces] = React.useState<Workspace[]>([])
  const [projects, setProjects] = React.useState<Project[]>([])
  const [dialog, setDialog] = React.useState<"workspace" | "project" | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    fetchWorkspaces()
      .then((items) => {
        setWorkspaces(items)
        if (!selectedWorkspace && items[0]) {
          onWorkspaceChange(items[0])
          persistWorkspace(items[0])
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load workspaces."))
      .finally(() => setLoading(false))
  }, [])

  React.useEffect(() => {
    if (!selectedWorkspace) {
      setProjects([])
      return
    }

    fetchProjects(selectedWorkspace.id)
      .then((items) => {
        setProjects(items)
        if (items[0]) onProjectChange(items[0])
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load projects."))
  }, [selectedWorkspace?.id])

  async function handleCreateWorkspace(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    const formData = new FormData(event.currentTarget)

    try {
      const nextWorkspace = await createWorkspace({
        name: String(formData.get("workspaceName") || ""),
      })
      setWorkspaces((items) => [nextWorkspace, ...items])
      setProjects([])
      onWorkspaceChange(nextWorkspace)
      persistWorkspace(nextWorkspace)
      setDialog(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create workspace.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCreateProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    const formData = new FormData(event.currentTarget)

    try {
      if (!selectedWorkspace) {
        throw new Error("Create a workspace before creating a project.")
      }
      const project = await createProject({
        name: String(formData.get("projectName") || ""),
        description: String(formData.get("projectDescription") || ""),
        workspaceId: selectedWorkspace.id,
      })
      setProjects((items) => [project, ...items])
      onProjectChange(project)
      onViewChange("projects")
      setDialog(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <aside className="relative z-[70] flex w-[52px] shrink-0 overflow-visible pr-2 sm:w-[58px]" aria-label="Primary navigation">
        <div className="app-panel flex h-full w-full flex-col items-center overflow-visible rounded-[20px] px-1.5 py-3 sm:rounded-[22px]">
          <nav className="flex min-h-0 flex-1 flex-col items-center gap-1 overflow-visible">
            {PRIMARY_NAV.map((item) => (
              <NavButton
                key={item.id}
                item={item}
                active={activeView === item.id}
                onClick={() => onViewChange(item.id)}
              />
            ))}
          </nav>

          <div className="mt-2 flex flex-col items-center gap-1.5 border-t border-border/70 pt-2">
            <button
              onClick={() => {
                setError(null)
                setDialog(selectedWorkspace ? "project" : "workspace")
              }}
              className="group relative flex h-9 w-9 items-center justify-center rounded-2xl bg-foreground text-background shadow-sm transition hover:opacity-90"
              aria-label={selectedWorkspace ? "Create project" : "Create workspace"}
            >
              <Plus className="h-5 w-5" aria-hidden="true" />
              <TooltipLabel>{selectedWorkspace ? "Create project" : "Create workspace"}</TooltipLabel>
            </button>
            {SECONDARY_NAV.map((item) => (
              <NavButton
                key={item.id}
                item={item}
                active={activeView === item.id}
                onClick={() => onViewChange(item.id)}
              />
            ))}
          </div>
        </div>
      </aside>

      {dialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--overlay)] px-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <form
            onSubmit={dialog === "workspace" ? handleCreateWorkspace : handleCreateProject}
          className="app-panel w-full max-w-md rounded-[28px] p-6"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-heading text-2xl font-bold tracking-tight">
                  {dialog === "workspace" ? "Create workspace" : "Create project"}
                </h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  {dialog === "workspace"
                    ? "Start a new company, team, or AI initiative."
                    : `Create a project inside ${selectedWorkspace?.name || "your workspace"}.`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDialog(null)}
                className="rounded-full p-2 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
                aria-label="Close dialog"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>

            <div className="mt-5 space-y-4">
              {dialog === "workspace" ? (
                <Field label="Workspace name" name="workspaceName" placeholder="Acme AI Lab" />
              ) : (
                <>
                  <Field label="Project name" name="projectName" placeholder="Customer churn reduction" />
                  <label className="block">
                    <span className="text-sm font-medium text-foreground">Description</span>
                    <textarea
                      name="projectDescription"
                      rows={3}
                      placeholder="Optional context for the project"
                      className="app-control mt-1.5 w-full resize-none rounded-2xl px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                    />
                  </label>
                </>
              )}

              {error && (
                <div className="rounded-2xl border border-error/30 bg-error-soft px-3 py-2 text-sm text-error" role="alert">
                  {error}
                </div>
              )}
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDialog(null)}
                className="app-control inline-flex h-10 items-center justify-center rounded-full px-5 text-sm font-semibold text-foreground"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="app-accent-shadow inline-flex h-10 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary-dark disabled:opacity-50"
              >
                {isSubmitting ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  )
}

function Field({ label, name, placeholder }: { label: string; name: string; placeholder: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground">{label}</span>
      <input
        name={name}
        required
        minLength={2}
        placeholder={placeholder}
        className="app-control mt-1.5 h-11 w-full rounded-full px-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
      />
    </label>
  )
}

function NavButton({
  item,
  active,
  onClick,
}: {
  item: NavItem
  active: boolean
  onClick: () => void
}) {
  const Icon = item.icon
  return (
    <button
      onClick={onClick}
      aria-label={item.label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-9 w-9 items-center justify-center rounded-xl text-foreground transition",
        active
          ? "bg-surface-raised text-foreground shadow-sm"
          : "text-muted-foreground hover:bg-surface-raised/70 hover:text-foreground",
      )}
    >
      <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
      <TooltipLabel>{item.label}</TooltipLabel>
    </button>
  )
}

function TooltipLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="app-panel-raised pointer-events-none absolute left-[calc(100%+0.6rem)] top-1/2 z-[80] -translate-y-1/2 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-semibold text-foreground opacity-0 transition duration-150 group-hover:translate-x-1 group-hover:opacity-100 group-focus-visible:translate-x-1 group-focus-visible:opacity-100">
      {children}
    </span>
  )
}
