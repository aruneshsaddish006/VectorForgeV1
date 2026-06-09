import { cn } from "@/lib/utils"
import { STATUS_META } from "@/lib/status"
import type { AgentStatus } from "@/lib/types"

export function StatusPill({
  status,
  className,
}: {
  status: AgentStatus
  className?: string
}) {
  const meta = STATUS_META[status]
  const Icon = meta.icon
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        meta.pill,
        className,
      )}
    >
      <Icon className={cn("h-3.5 w-3.5", meta.spin && "animate-spin")} aria-hidden="true" />
      {meta.label}
    </span>
  )
}
