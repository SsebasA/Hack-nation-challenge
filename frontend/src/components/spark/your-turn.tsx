import { Hand } from "lucide-react"
import { cn } from "@/lib/utils"

// The one consistent visual for "a human must act here".
export function YourTurn({
  title,
  children,
  className,
}: {
  title: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("rounded-xl border-2 border-amber-300 bg-amber-50/60 p-4", className)}>
      <div className="mb-2 flex items-center gap-2">
        <span className="inline-flex size-6 items-center justify-center rounded-full bg-amber-400 text-amber-950">
          <Hand className="size-3.5" />
        </span>
        <span className="text-xs font-semibold tracking-wide text-amber-800 uppercase">Your turn</span>
      </div>
      <p className="mb-3 text-sm font-medium">{title}</p>
      {children}
    </div>
  )
}
