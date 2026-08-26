import { cn } from "@/lib/utils"
import type { Team } from "@/lib/data"

export function TeamLogo({
  team,
  size = 44,
  className,
}: {
  team: Team
  size?: number
  className?: string
}) {
  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center rounded-full font-mono font-bold tracking-tight text-white shadow-lg ring-1 ring-white/15",
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.32,
        background: `radial-gradient(120% 120% at 30% 20%, ${team.color}, color-mix(in srgb, ${team.color} 45%, #0b1220))`,
      }}
      aria-hidden="true"
    >
      {team.abbr}
    </div>
  )
}
