"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  ChevronRight,
  PanelRightOpen,
  PanelRightClose,
  Search,
  Bell,
  ShieldCheck,
  Moon,
  Sun,
  LogOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { logoutUser } from "@/lib/api"

type Theme = "light" | "dark"

function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "light"

  const stored = window.localStorage.getItem("theme")
  if (stored === "light" || stored === "dark") return stored

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function TopBar({
  inspectorOpen,
  onToggleInspector,
}: {
  inspectorOpen: boolean
  onToggleInspector: () => void
}) {
  const router = useRouter()
  const [theme, setTheme] = useState<Theme | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)

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

  async function handleLogout() {
    setLoggingOut(true)
    await logoutUser()
    router.push("/login")
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-surface px-4">
      {/* Breadcrumb */}
      <div className="flex min-w-0 items-center gap-1.5 text-sm">
        <span className="hidden text-muted-foreground sm:inline">Customer Intelligence</span>
        <ChevronRight className="hidden h-4 w-4 text-muted-foreground sm:inline" aria-hidden="true" />
        <span className="truncate font-semibold text-foreground">Churn Prediction Use Case</span>
        <span className="ml-2 hidden items-center gap-1 rounded-md bg-success-soft px-2 py-0.5 text-[11px] font-medium text-success md:inline-flex">
          <ShieldCheck className="h-3 w-3" aria-hidden="true" />
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
            className="h-9 w-56 rounded-lg border border-border bg-surface-muted/60 pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:bg-surface"
          />
        </div>

        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative">
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
        >
          {isDark ? (
            <Sun className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Moon className="h-5 w-5" aria-hidden="true" />
          )}
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleInspector}
          aria-label={inspectorOpen ? "Hide inspector" : "Show inspector"}
          className={cn(inspectorOpen && "bg-surface-muted text-foreground")}
        >
          {inspectorOpen ? (
            <PanelRightClose className="h-5 w-5" aria-hidden="true" />
          ) : (
            <PanelRightOpen className="h-5 w-5" aria-hidden="true" />
          )}
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={handleLogout}
          disabled={loggingOut}
          aria-label="Log out"
          title="Log out"
        >
          <LogOut className="h-5 w-5" aria-hidden="true" />
        </Button>

        <span
          className="ml-1 flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-xs font-semibold text-background"
          aria-label="Jordan Ellis account"
        >
          JE
        </span>
      </div>
    </header>
  )
}
