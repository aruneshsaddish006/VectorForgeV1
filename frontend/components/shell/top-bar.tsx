"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
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
import { type Project, type Workspace } from "@/lib/api"

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
  const [theme, setTheme] = useState<Theme | null>(null)

  useEffect(() => {
    setTheme(getInitialTheme())
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

  const workspaceName = selectedWorkspace?.name || "Select workspace"
  const projectName = selectedProject?.name || "Select project"

  return (
    <header className="app-panel relative z-[100] flex min-h-20 shrink-0 items-center justify-between gap-3 rounded-[24px] px-3 sm:gap-4 sm:px-5">
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-2xl px-1.5 py-1 text-left transition hover:bg-surface-raised/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          aria-label="Go to landing page"
        >
          <ForgeAiIcon size="lg" priority className="rounded-full" />
          <div className="hidden leading-none sm:block">
            <div className="font-heading text-2xl font-bold tracking-tight text-foreground">Forge AI</div>
            <div className="mt-1 text-[11px] font-bold uppercase tracking-[0.22em] text-primary">
              AI Strategy Platform
            </div>
          </div>
        </Link>

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

      </div>
    </header>
  )
}
