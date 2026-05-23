import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export function ReviewerPageHeader({
  title,
  description,
  action,
  className,
}: {
  title: string
  description: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("mb-7 flex items-start justify-between gap-4", className)}>
      <div>
        <h1 className="text-xl font-semibold text-gray-800">{title}</h1>
        <p className="mt-0.5 text-sm text-[rgba(0,0,0,0.4)]">{description}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

export function ReviewerSurfaceCard({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("overflow-hidden rounded-xl bg-white shadow-sm", className)}>
      {children}
    </div>
  )
}
