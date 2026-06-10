"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { logoutUser } from "@/lib/api"

type StoredUser = {
  fullName?: string
  email?: string
}

export function UserMenuButton() {
  const router = useRouter()
  const [open, setOpen] = React.useState(false)
  const [user, setUser] = React.useState<StoredUser | null>(null)
  const containerRef = React.useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    try {
      const stored = window.localStorage.getItem("forge_ai_user")
      setUser(stored ? JSON.parse(stored) : null)
    } catch {
      setUser(null)
    }
  }, [])

  React.useEffect(() => {
    if (!open) return

    function handlePointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener("pointerdown", handlePointerDown)
    return () => document.removeEventListener("pointerdown", handlePointerDown)
  }, [open])

  async function handleLogout() {
    await logoutUser()
    router.replace("/login")
  }

  const accountName = user?.fullName || "Signed in user"
  const accountEmail = user?.email || "No email available"
  const accountInitial = accountName.trim().charAt(0).toUpperCase() || "U"

  return (
    <div ref={containerRef} className="group relative">
      <button
        onClick={() => setOpen((current) => !current)}
        className="app-accent-shadow flex h-10 w-10 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground ring-4 ring-surface-raised/80"
        aria-label="Open account menu"
        aria-expanded={open}
      >
        {accountInitial}
      </button>

      {!open && (
        <span className="app-panel-raised pointer-events-none absolute left-[calc(100%+0.6rem)] top-1/2 z-[90] -translate-y-1/2 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-semibold text-foreground opacity-0 transition duration-150 group-hover:translate-x-1 group-hover:opacity-100 group-focus-within:translate-x-1 group-focus-within:opacity-100">
          Account
        </span>
      )}

      {open && (
        <div className="app-panel-raised absolute bottom-0 left-[calc(100%+0.75rem)] z-[140] w-72 rounded-2xl p-3">
          <div className="flex items-center gap-3 border-b border-border pb-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-base font-bold text-primary-foreground">
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
  )
}
