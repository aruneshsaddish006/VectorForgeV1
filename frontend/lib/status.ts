import {
  CircleDashed,
  Clock4,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Rocket,
  type LucideIcon,
} from "lucide-react"
import type { AgentStatus } from "./types"

type StatusMeta = {
  label: string
  icon: LucideIcon
  /** tailwind classes for the pill */
  pill: string
  /** dot/icon color class */
  accent: string
  spin?: boolean
}

export const STATUS_META: Record<AgentStatus, StatusMeta> = {
  draft: {
    label: "Draft",
    icon: CircleDashed,
    pill: "bg-surface-muted text-muted-foreground border-border",
    accent: "text-muted-foreground",
  },
  "waiting-approval": {
    label: "Waiting approval",
    icon: Clock4,
    pill: "bg-warning-soft text-warning border-warning/30",
    accent: "text-warning",
  },
  running: {
    label: "Running",
    icon: Loader2,
    pill: "bg-info-soft text-info border-info/30",
    accent: "text-info",
    spin: true,
  },
  complete: {
    label: "Complete",
    icon: CheckCircle2,
    pill: "bg-success-soft text-success border-success/30",
    accent: "text-success",
  },
  "needs-attention": {
    label: "Needs attention",
    icon: AlertTriangle,
    pill: "bg-warning-soft text-warning border-warning/30",
    accent: "text-warning",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    pill: "bg-error-soft text-error border-error/30",
    accent: "text-error",
  },
  deployed: {
    label: "Deployed",
    icon: Rocket,
    pill: "bg-info-soft text-info border-info/30",
    accent: "text-info",
  },
}
