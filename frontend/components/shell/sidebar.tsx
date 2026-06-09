"use client"

import * as React from "react"
import {
  LayoutGrid,
  FolderKanban,
  Lightbulb,
  Database,
  Cpu,
  Network,
  CloudCog,
  CreditCard,
  Activity,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Hexagon,
  ChevronsUpDown,
  Plus,
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
  badge?: string
}

const PRIMARY_NAV: NavItem[] = [
  { id: "workspaces", label: "Workspaces", icon: LayoutGrid },
  { id: "projects", label: "Projects", icon: FolderKanban, badge: "3" },
  { id: "use-cases", label: "Use Cases", icon: Lightbulb },
  { id: "datasets", label: "Datasets", icon: Database, badge: "2" },
  { id: "models", label: "Models", icon: Cpu },
  { id: "rag", label: "RAG Pipelines", icon: Network },
  { id: "deployments", label: "Deployments", icon: CloudCog },
]

const SECONDARY_NAV: NavItem[] = [
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "activity", label: "Activity Log", icon: Activity },
  { id: "settings", label: "Settings", icon: Settings },
]

export function Sidebar({
  selectedWorkspace,
  selectedProject,
  onWorkspaceChange,
  onProjectChange,
}: {
  selectedWorkspace: Workspace | null
  selectedProject: Project | null
  onWorkspaceChange: (workspace: Workspace) => void
  onProjectChange: (project: Project) => void
}) {
  const [collapsed, setCollapsed] = React.useState(false)
  const [active, setActive] = React.useState("use-cases")
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
      setActive("projects")
      setDialog(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const workspaceName = selectedWorkspace?.name || (loading ? "Loading..." : "Create workspace")
  const workspacePlan = selectedWorkspace?.plan || "No workspace selected"
  const workspaceInitials = workspaceName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "WS"

  return (
    <>
      <aside
        className={cn(
          "hidden shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200 lg:flex",
          collapsed ? "w-[68px]" : "w-64",
        )}
        aria-label="Primary navigation"
      >
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Hexagon className="h-5 w-5" aria-hidden="true" />
        </span>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-foreground">Forge AI</div>
            <div className="truncate text-[11px] text-muted-foreground">AI Strategy Platform</div>
          </div>
        )}
      </div>

      {/* Workspace switcher */}
      {!collapsed && (
        <div className="space-y-2 px-3 pt-3">
          <button className="flex w-full items-center gap-2.5 rounded-lg border border-border bg-surface-muted/60 px-2.5 py-2 text-left hover:bg-surface-muted">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-foreground text-xs font-semibold text-background">
              {workspaceInitials}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-foreground">{workspaceName}</span>
              <span className="block truncate text-[11px] text-muted-foreground">{workspacePlan}</span>
            </span>
            <ChevronsUpDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          </button>
          <button
            onClick={() => {
              setError(null)
              setDialog("workspace")
            }}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground hover:bg-surface-muted"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            Create workspace
          </button>
          {workspaces.length > 1 && (
            <div className="space-y-1">
              {workspaces.slice(0, 3).map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    onWorkspaceChange(item)
                    persistWorkspace(item)
                  }}
                  className={cn(
                    "w-full truncate rounded-lg px-2.5 py-1.5 text-left text-xs hover:bg-surface-muted",
                    item.id === selectedWorkspace?.id ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  {item.name}
                </button>
              ))}
            </div>
          )}
          {selectedWorkspace && (
            <div className="space-y-1 border-t border-border pt-2">
              <div className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Projects
              </div>
              {projects.length === 0 ? (
                <div className="px-1 text-xs leading-5 text-muted-foreground">Create a project to see datasets and models.</div>
              ) : (
                projects.slice(0, 4).map((project) => (
                  <button
                    key={project.id}
                    onClick={() => {
                      onProjectChange(project)
                      setActive("projects")
                    }}
                    className={cn(
                      "w-full truncate rounded-lg px-2.5 py-1.5 text-left text-xs hover:bg-surface-muted",
                      project.id === selectedProject?.id ? "bg-info-soft text-primary" : "text-muted-foreground",
                    )}
                  >
                    {project.name}
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      )}

      <nav className="scroll-thin flex-1 overflow-y-auto px-3 py-3">
        {!collapsed && (
          <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Workspace
          </p>
        )}
        <ul className="flex flex-col gap-0.5">
          {PRIMARY_NAV.map((item) => (
            <NavRow
              key={item.id}
              item={
                item.id === "projects"
                  ? { ...item, badge: String(projects.length) }
                  : item.id === "datasets" || item.id === "models"
                    ? { ...item, badge: selectedProject ? "1" : "0" }
                    : item
              }
              active={active === item.id}
              collapsed={collapsed}
              onClick={() => setActive(item.id)}
            />
          ))}
        </ul>

        <div className="my-3 h-px bg-border" />
        {!collapsed && (
          <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Account
          </p>
        )}
        <ul className="flex flex-col gap-0.5">
          {SECONDARY_NAV.map((item) => (
            <NavRow
              key={item.id}
              item={item}
              active={active === item.id}
              collapsed={collapsed}
              onClick={() => setActive(item.id)}
            />
          ))}
        </ul>
      </nav>

      {/* New project + collapse */}
      <div className="border-t border-border p-3">
        {!collapsed && (
          <button
            onClick={() => {
              setError(null)
              setDialog("project")
            }}
            disabled={!selectedWorkspace}
            className="mb-2 flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-dark"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            New Project
          </button>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-surface-muted hover:text-foreground"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" aria-hidden="true" />
          ) : (
            <>
              <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
              Collapse
            </>
          )}
        </button>
      </div>
      </aside>

      {dialog && (
        <div className="fixed inset-0 z-50 hidden items-center justify-center bg-black/50 px-4 lg:flex" role="dialog" aria-modal="true">
          <form
            onSubmit={dialog === "workspace" ? handleCreateWorkspace : handleCreateProject}
            className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold tracking-tight">
                  {dialog === "workspace" ? "Create workspace" : "Create project"}
                </h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  {dialog === "workspace"
                    ? "Start a new company or team workspace."
                    : `Create a project inside ${selectedWorkspace?.name || "your workspace"}.`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDialog(null)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
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
                      className="mt-1.5 w-full resize-none rounded-lg border border-border bg-surface-muted/60 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                    />
                  </label>
                </>
              )}

              {error && (
                <div className="rounded-lg border border-error/30 bg-error-soft px-3 py-2 text-sm text-error" role="alert">
                  {error}
                </div>
              )}
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDialog(null)}
                className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-surface px-4 text-sm font-medium text-foreground hover:bg-surface-muted"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex h-9 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary-dark disabled:opacity-50"
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
        className="mt-1.5 h-10 w-full rounded-lg border border-border bg-surface-muted/60 px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
      />
    </label>
  )
}

function NavRow({
  item,
  active,
  collapsed,
  onClick,
}: {
  item: NavItem
  active: boolean
  collapsed: boolean
  onClick: () => void
}) {
  const Icon = item.icon
  return (
    <li>
      <button
        onClick={onClick}
        aria-current={active ? "page" : undefined}
        title={collapsed ? item.label : undefined}
        className={cn(
          "group flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
          collapsed && "justify-center px-0",
          active
            ? "bg-info-soft text-primary"
            : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
        )}
      >
        <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
        {!collapsed && <span className="flex-1 text-left">{item.label}</span>}
        {!collapsed && item.badge && (
          <span
            className={cn(
              "rounded-md px-1.5 py-0.5 text-[11px] font-semibold tabular-nums",
              active ? "bg-primary text-primary-foreground" : "bg-surface-muted text-muted-foreground",
            )}
          >
            {item.badge}
          </span>
        )}
      </button>
    </li>
  )
}
