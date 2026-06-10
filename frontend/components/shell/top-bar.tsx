"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  ChevronRight,
  Search,
  Bell,
  HelpCircle,
  ShieldCheck,
  Moon,
  Sun,
} from "lucide-react"
import { ForgeAiIcon } from "@/components/brand/forge-ai-icon"
import { Button } from "@/components/ui/button"
import { logoutUser, type Project, type Workspace } from "@/lib/api"

type Theme = "light" | "dark"

function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "light"

  const stored = window.localStorage.getItem("theme")
  if (stored === "light" || stored === "dark") return stored

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function TopBar({
  selectedWorkspace,
  selectedProject,
}: {
  selectedWorkspace: Workspace | null
  selectedProject: Project | null
}) {
  const router = useRouter()
  const [theme, setTheme] = useState<Theme | null>(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [user, setUser] = useState<{ fullName?: string; email?: string } | null>(null)

  useEffect(() => {
    setTheme(getInitialTheme())
    try {
      const stored = window.localStorage.getItem("forge_ai_user")
      setUser(stored ? JSON.parse(stored) : null)
    } catch {
      setUser(null)
    }
  }, [])

  useEffect(() => {
    if (!theme) return

    document.documentElement.dataset.theme = theme
    window.localStorage.setItem("theme", theme)
  }, [theme])

  const isDark = theme === "dark"

  function toggleTheme() {
    const currentTheme =
      theme || (document.documentElement.dataset.theme === "dark" ? "dark" : "light")

    setTheme(currentTheme === "dark" ? "light" : "dark")
  }

  async function handleLogout() {
    await logoutUser()
    router.replace("/login")
  }

  const workspaceName = selectedWorkspace?.name || "Select workspace"
  const projectName = selectedProject?.name || "Select project"
  const accountName = user?.fullName || "Signed in user"
  const accountEmail = user?.email || "No email available"
  const accountInitial = accountName.trim().charAt(0).toUpperCase() || "U"

  return (
    <header className="app-panel relative z-[100] flex min-h-20 shrink-0 items-center justify-between gap-3 rounded-[24px] px-3 sm:gap-4 sm:px-5">
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        <div className="flex items-center gap-2.5">
          <ForgeAiIcon size="lg" priority className="rounded-full" />
          <div className="hidden leading-none sm:block">
            <div className="font-heading text-2xl font-bold tracking-tight text-foreground">Forge AI</div>
            <div className="mt-1 text-[11px] font-bold uppercase tracking-[0.22em] text-primary">
              AI Strategy Platform
            </div>
          </div>
        </div>

        <div className="app-control flex min-w-0 items-center gap-1.5 rounded-full px-3 py-2 text-xs sm:gap-2 sm:px-4 sm:text-sm">
          <span className="max-w-48 truncate font-semibold text-foreground">{workspaceName}</span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="max-w-56 truncate font-semibold text-foreground">{projectName}</span>
        </div>

        <span className="hidden items-center gap-1 rounded-full bg-success-soft px-3 py-1 text-[11px] font-semibold text-success lg:inline-flex">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
          Approver role
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <div className="relative hidden md:block">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Search projects, datasets…"
            aria-label="Search"
            className="app-control h-10 w-56 rounded-full pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:bg-surface-raised"
          />
        </div>

        <Button variant="ghost" size="icon" aria-label="Help" title="Help" className="hidden rounded-full sm:inline-flex">
          <HelpCircle className="h-5 w-5" aria-hidden="true" />
        </Button>

        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative hidden rounded-full sm:inline-flex">
          <Bell className="h-5 w-5" aria-hidden="true" />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-warning" />
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
          aria-pressed={isDark}
          title={isDark ? "Switch to light theme" : "Switch to dark theme"}
          className="rounded-full"
        >
          {isDark ? (
            <Sun className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Moon className="h-5 w-5" aria-hidden="true" />
          )}
        </Button>

        <div className="relative ml-1">
          <button
            onClick={() => setAccountOpen((open) => !open)}
            className="app-accent-shadow flex h-11 w-11 items-center justify-center rounded-full bg-primary text-base font-bold text-primary-foreground ring-4 ring-surface-raised/80"
            aria-label="Open account menu"
            aria-expanded={accountOpen}
          >
            {accountInitial}
          </button>

          {accountOpen && (
            <div className="app-panel-raised absolute right-0 top-[calc(100%+0.75rem)] z-[120] w-64 rounded-2xl p-3">
              <div className="flex items-center gap-3 border-b border-border pb-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-sm font-bold text-primary-foreground">
                  {accountInitial}
                </span>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-foreground">{accountName}</div>
                  <div className="truncate text-xs text-muted-foreground">{accountEmail}</div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="mt-2 flex w-full items-center justify-center rounded-xl px-3 py-2 text-sm font-semibold text-error transition hover:bg-error-soft"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
