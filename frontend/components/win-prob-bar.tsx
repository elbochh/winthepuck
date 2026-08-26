"use client"

import { motion } from "framer-motion"
import type { Team } from "@/lib/data"

export function WinProbBar({
  home,
  away,
  homeProb,
}: {
  home: Team
  away: Team
  homeProb: number
}) {
  const awayProb = 100 - homeProb

  return (
    <div>
      <div className="mb-2 flex items-end justify-between text-sm">
        <div className="flex items-center gap-2">
          <span
            className="size-2.5 rounded-full"
            style={{ background: home.color }}
          />
          <span className="font-semibold">{home.abbr}</span>
          <motion.span
            key={`h-${homeProb}`}
            initial={{ scale: 1.25, color: "var(--primary)" }}
            animate={{ scale: 1, color: "var(--foreground)" }}
            className="font-mono font-bold tabular-nums"
          >
            {homeProb}%
          </motion.span>
        </div>
        <div className="flex items-center gap-2">
          <motion.span
            key={`a-${awayProb}`}
            initial={{ scale: 1.25, color: "var(--primary)" }}
            animate={{ scale: 1, color: "var(--foreground)" }}
            className="font-mono font-bold tabular-nums"
          >
            {awayProb}%
          </motion.span>
          <span className="font-semibold">{away.abbr}</span>
          <span
            className="size-2.5 rounded-full"
            style={{ background: away.color }}
          />
        </div>
      </div>

      <div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary ring-1 ring-inset ring-border">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            background: `linear-gradient(90deg, ${home.color}, color-mix(in srgb, ${home.color} 70%, #fff))`,
          }}
          animate={{ width: `${homeProb}%` }}
          transition={{ type: "spring", stiffness: 90, damping: 18 }}
        />
        <motion.div
          className="absolute inset-y-0 right-0 rounded-full opacity-90"
          style={{
            background: `linear-gradient(270deg, ${away.color}, color-mix(in srgb, ${away.color} 70%, #fff))`,
          }}
          animate={{ width: `${awayProb}%` }}
          transition={{ type: "spring", stiffness: 90, damping: 18 }}
        />
        <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-background/60" />
      </div>
    </div>
  )
}
