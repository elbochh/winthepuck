"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { ShieldCheck, Sparkles } from "lucide-react"
import { SectionHeading } from "@/components/section-heading"
import { TeamLogo } from "@/components/team-logo"
import { ConfidenceRing } from "@/components/confidence-ring"
import type { Game, TeamStats } from "@/lib/data"

const ROWS: { key: keyof TeamStats; label: string; max: number; suffix?: string }[] = [
  { key: "goalsFor", label: "Goals / game", max: 5 },
  { key: "goalsAgainst", label: "Goals against", max: 5 },
  { key: "powerPlay", label: "Power play", max: 35, suffix: "%" },
  { key: "penaltyKill", label: "Penalty kill", max: 100, suffix: "%" },
  { key: "shotsPerGame", label: "Shots / game", max: 40 },
  { key: "faceoffWin", label: "Faceoff win", max: 65, suffix: "%" },
]

export function MatchupComparison({ games }: { games: Game[] }) {
  const [active, setActive] = useState(games[0]?.id)
  const game = games.find((g) => g.id === active) ?? games[0]
  if (!game) return null
  const favored = game.homeWinProb >= 50 ? game.home : game.away
  const edge = game.homeWinProb >= 50 ? game.homeWinProb : 100 - game.homeWinProb

  return (
    <section id="matchups" className="mx-auto w-full max-w-6xl px-4 py-16 sm:py-20">
      <SectionHeading
        eyebrow="Head to head"
        title="Team comparison & confidence"
        description="Dive into the underlying metrics behind each prediction and see how confident the model is in the call."
        action={
          <div className="flex flex-wrap gap-2">
            {games.map((g) => (
              <button
                key={g.id}
                onClick={() => setActive(g.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  g.id === active
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                }`}
              >
                {g.home.abbr} v {g.away.abbr}
              </button>
            ))}
          </div>
        }
      />

      <motion.div
        key={game.id}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="grid gap-5 lg:grid-cols-[1fr_320px]"
      >
        {/* stat bars */}
        <div className="glass rounded-3xl border border-border p-5 sm:p-7">
          <div className="mb-6 flex items-center justify-between">
            <TeamHead team={game.home} />
            <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Matchup
            </span>
            <TeamHead team={game.away} reverse />
          </div>

          <div className="space-y-4">
            {ROWS.map((row, i) => {
              const hv = game.homeStats[row.key] as number
              const av = game.awayStats[row.key] as number
              const better = row.key === "goalsAgainst" ? hv < av : hv > av
              return (
                <div key={row.key}>
                  <div className="mb-1.5 flex items-center justify-between text-sm">
                    <span
                      className={`font-mono font-semibold tabular-nums ${better ? "text-primary" : "text-muted-foreground"}`}
                    >
                      {hv}
                      {row.suffix}
                    </span>
                    <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {row.label}
                    </span>
                    <span
                      className={`font-mono font-semibold tabular-nums ${!better ? "text-chart-2" : "text-muted-foreground"}`}
                    >
                      {av}
                      {row.suffix}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="flex h-2.5 flex-1 justify-end overflow-hidden rounded-full bg-secondary">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ background: game.home.color }}
                        initial={{ width: 0 }}
                        whileInView={{ width: `${(hv / row.max) * 100}%` }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.8, delay: i * 0.05 }}
                      />
                    </div>
                    <div className="flex h-2.5 flex-1 overflow-hidden rounded-full bg-secondary">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ background: game.away.color }}
                        initial={{ width: 0 }}
                        whileInView={{ width: `${(av / row.max) * 100}%` }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.8, delay: i * 0.05 }}
                      />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* confidence panel */}
        <div className="glass flex flex-col items-center justify-center rounded-3xl border border-border p-7 text-center">
          <span className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/15 px-3 py-1 text-xs font-semibold text-primary">
            <Sparkles className="size-3.5" /> Prediction confidence
          </span>
          <ConfidenceRing value={game.confidence} size={140} stroke={12} label={false} />
          <div className="-mt-[88px] mb-[36px] flex flex-col items-center">
            <span className="font-mono text-4xl font-bold tabular-nums">
              {game.confidence}
              <span className="text-xl text-muted-foreground">%</span>
            </span>
          </div>
          <div className="flex items-center gap-2 rounded-xl bg-secondary/60 px-4 py-3">
            <TeamLogo team={favored} size={32} />
            <div className="text-left">
              <p className="text-sm font-bold leading-tight">
                {favored.city} {favored.name}
              </p>
              <p className="text-xs text-muted-foreground">
                Projected winner · {edge}% win prob
              </p>
            </div>
          </div>
          <p className="mt-4 flex items-start gap-2 text-left text-xs leading-relaxed text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-chart-3" />
            Confidence is the ensemble&apos;s probability for its pick. Team stats
            are full-season 2025–26 averages from official NHL game data.
          </p>
        </div>
      </motion.div>
    </section>
  )
}

function TeamHead({ team, reverse }: { team: Game["home"]; reverse?: boolean }) {
  return (
    <div className={`flex items-center gap-3 ${reverse ? "flex-row-reverse" : ""}`}>
      <TeamLogo team={team} size={44} />
      <div className={reverse ? "text-right" : ""}>
        <div className="font-bold leading-tight">{team.abbr}</div>
        <div className="text-xs text-muted-foreground">{team.record}</div>
      </div>
    </div>
  )
}
