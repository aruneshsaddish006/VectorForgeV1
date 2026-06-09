import Image from "next/image"
import { cn } from "@/lib/utils"

type ForgeAiIconSize = "sm" | "md" | "lg" | "xl"

const SIZE_CLASS: Record<ForgeAiIconSize, string> = {
  sm: "h-8 w-8",
  md: "h-9 w-9",
  lg: "h-11 w-11",
  xl: "h-16 w-16",
}

export function ForgeAiIcon({
  size = "md",
  className,
  priority = false,
}: {
  size?: ForgeAiIconSize
  className?: string
  priority?: boolean
}) {
  return (
    <span
      className={cn(
        "app-accent-shadow relative inline-flex shrink-0 overflow-hidden rounded-2xl bg-surface-raised ring-1 ring-border",
        SIZE_CLASS[size],
        className,
      )}
      aria-hidden="true"
    >
      <Image
        src="/brand/neural-net.gif"
        alt=""
        fill
        priority={priority}
        unoptimized
        className="object-cover"
        sizes="64px"
      />
    </span>
  )
}
