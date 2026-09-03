"use client"

import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import {
  Target,
  Gauge,
  Sigma,
  CalendarDays,
  Check,
  X,
  ChevronDown,
} from "lucide-react"
import { SectionHeading } from "@/components/section-heading"
import type { SeasonData, SeasonGame } from "@/lib/data"

const MONTH_LABELS: Record<string, string> = {
  "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May",
  "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct",
  "11": "Nov", "12": "Dec",
}

function monthLabel(ym: string) {
  const [y, m] = ym.split("-")
  return `${MONTH_LABELS[m] ?? m} ${y.slice(2)}`
}

export function SeasonReview({
  season,
  teamColors,
}: {
  season: SeasonData
  teamColors: Record<string, string>
}) {
  const s = season.summary

  const cards = [
    {
      label: "All-game accuracy",
      value: `${(100 * s.accuracy).toFixed(1)}%`,
      sub: `${s.games.toLocaleString()} games, every one predicted before puck drop`,
      icon: Target,
    },
    {
      label: "Confident picks (≥60%)",
      value: `${(100 * s.highConfidenceAccuracy).toFixed(1)}%`,
      sub: `${s.highConfidenceGames.toLocaleString()} picks where the model was most sure`,
      icon: Gauge,
    },
    {
      label: "Log loss",
      value: s.logLoss.toFixed(3),
      sub: "Probability quality (lower is better; 0.693 = coin flip)",
      icon: Sigma,
    },
    {
      label: "Season",
      value: season.season,
      sub: "Regular season + playoffs, walk-forward tested",
      icon: CalendarDays,
    },
  ]

  return (
    <div className="mx-auto w-full max-w-6xl px-4 pt-32 pb-16">
      <SectionHeading
        eyebrow="Season review"
        title={`How the model did in ${season.season}`}
        description="These are genuine out-of-sample predictions: for each month, the model was trained only on games that finished before that month began, then graded on what happened next."
      />

      {/* summary cards */}
      <div className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c, i) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.06 }}
            className="glass rounded-2xl border border-border p-5"
          >
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <c.icon className="size-4 text-primary" />
              {c.label}
            </div>
            <div className="mt-2 font-mono text-3xl font-bold tabular-nums">
              {c.value}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {c.sub}
            </p>
          </motion.div>
        ))}
      </div>

      <div className="mb-10 grid gap-5 lg:grid-cols-2">
        {/* monthly accuracy */}
        <div className="glass rounded-3xl border border-border p-6">
          <h3 className="mb-1 font-bold">Accuracy by month</h3>
          <p className="mb-5 text-xs text-muted-foreground">
            Dashed line = 50% (coin flip). NHL games are hard: even bookmakers
            sit near 59–60%.
          </p>
          <MonthlyChart monthly={season.monthly} />
        </div>

        {/* calibration by confidence */}
        <div className="glass rounded-3xl border border-border p-6">
          <h3 className="mb-1 font-bold">The more confident, the more correct</h3>
          <p className="mb-5 text-xs text-muted-foreground">
            Grouping every prediction by the model&apos;s stated confidence. A
            well-calibrated model should win more often exactly when it claims
            to be more sure.
          </p>
          <div className="space-y-4">
            {season.confidenceBuckets.map((b) => {
              const pct = 100 * b.accuracy
              return (
                <div key={b.range}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium text-muted-foreground">
                      Confidence {b.range}
                      <span className="ml-2 text-muted-foreground/60">
                        {b.n} games
                      </span>
                    </span>
                    <span className="font-mono font-bold text-primary">
                      {pct.toFixed(1)}% correct
                    </span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-secondary">
                    <motion.div
                      initial={{ width: 0 }}
                      whileInView={{ width: `${pct}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.7 }}
                      className="h-full rounded-full bg-gradient-to-r from-primary/60 to-chart-3"
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <GameExplorer games={season.games} teamColors={teamColors} />
    </div>
  )
}

function MonthlyChart({
  monthly,
}: {
  monthly: { month: string; n: number; accuracy: number }[]
}) {
  const W = 560
  const H = 200
  const PAD_B = 22
  const PAD_T = 14
  const maxPct = 75
  const bw = W / monthly.length

  const y = (pct: number) => PAD_T + (1 - pct / maxPct) * (H - PAD_T - PAD_B)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
      aria-label="Model accuracy by month">
      {[25, 50, 75].map((g) => (
        <g key={g}>
          <line
            x1={0} x2={W} y1={y(g)} y2={y(g)}
            stroke={g === 50 ? "var(--live)" : "var(--border)"}
            strokeOpacity={g === 50 ? 0.5 : 1}
            strokeDasharray={g === 50 ? "4 4" : undefined}
          />
          <text x={W - 2} y={y(g) - 3} textAnchor="end"
            className="fill-muted-foreground" fontSize="9">
            {g}%
          </text>
        </g>
      ))}
      {monthly.map((m, i) => {
        const pct = 100 * m.accuracy
        return (
          <g key={m.month}>
            <motion.rect
              x={i * bw + bw * 0.18}
              width={bw * 0.64}
              rx={4}
              fill="var(--primary)"
              fillOpacity={0.85}
              initial={{ y: y(0), height: 0 }}
              whileInView={{ y: y(pct), height: y(0) - y(pct) }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.04 }}
            >
              <title>{`${monthLabel(m.month)}: ${pct.toFixed(1)}% over ${m.n} games`}</title>
            </motion.rect>
            <text
              x={i * bw + bw / 2} y={y(pct) - 4} textAnchor="middle"
              className="fill-foreground" fontSize="9" fontWeight="bold"
            >
              {pct.toFixed(0)}
            </text>
            <text
              x={i * bw + bw / 2} y={H - 6} textAnchor="middle"
              className="fill-muted-foreground" fontSize="9"
            >
              {monthLabel(m.month)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function GameExplorer({
  games,
  teamColors,
}: {
  games: SeasonGame[]
  teamColors: Record<string, string>
}) {
  const [month, setMonth] = useState<string>("all")
  const [team, setTeam] = useState<string>("all")
  const [outcome, setOutcome] = useState<string>("all")
  const [limit, setLimit] = useState(30)

  const months = useMemo(
    () => [...new Set(games.map((g) => g.date.slice(0, 7)))],
    [games],
  )
  const teams = useMemo(
    () => [...new Set(games.flatMap((g) => [g.home, g.away]))].sort(),
    [games],
  )

  const filtered = useMemo(
    () =>
      games.filter(
        (g) =>
          (month === "all" || g.date.startsWith(month)) &&
          (team === "all" || g.home === team || g.away === team) &&
          (outcome === "all" ||
            (outcome === "correct" ? g.correct : !g.correct)),
      ),
    [games, month, team, outcome],
  )
  const shown = filtered.slice(-limit).reverse()
  const acc = filtered.length
    ? (100 * filtered.filter((g) => g.correct).length) / filtered.length
    : 0

  const selectCls =
    "rounded-lg border border-border bg-secondary px-3 py-2 text-xs font-semibold text-foreground outline-none focus:ring-1 focus:ring-primary"

  return (
    <div className="glass rounded-3xl border border-border p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-bold">Every prediction, every game</h3>
          <p className="text-xs text-muted-foreground">
            {filtered.length.toLocaleString()} games match ·{" "}
            <span className="font-semibold text-primary">
              {acc.toFixed(1)}% correct
            </span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className={selectCls}
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            aria-label="Filter by month"
          >
            <option value="all">All months</option>
            {months.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m)}
              </option>
            ))}
          </select>
          <select
            className={selectCls}
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            aria-label="Filter by team"
          >
            <option value="all">All teams</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            className={selectCls}
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            aria-label="Filter by outcome"
          >
            <option value="all">Hits & misses</option>
            <option value="correct">Correct picks</option>
            <option value="wrong">Missed picks</option>
          </select>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border">
        <div className="hidden grid-cols-[90px_1fr_120px_1fr_90px_70px] items-center gap-2 border-b border-border bg-secondary/40 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground sm:grid">
          <span>Date</span>
          <span className="text-right">Away</span>
          <span className="text-center">Score</span>
          <span>Home</span>
          <span className="text-right">Home prob</span>
          <span className="text-right">Pick</span>
        </div>
        {shown.map((g) => (
          <div
            key={g.id}
            className="grid grid-cols-2 items-center gap-2 border-b border-border px-4 py-2.5 text-sm last:border-0 hover:bg-secondary/40 sm:grid-cols-[90px_1fr_120px_1fr_90px_70px]"
          >
            <span className="font-mono text-xs text-muted-foreground">
              {g.date.slice(5)}
              {g.playoff && (
                <span className="ml-1 rounded bg-chart-4/20 px-1 text-[9px] font-bold text-chart-4">
                  PO
                </span>
              )}
            </span>
            <span className="text-right font-semibold">
              <TeamTag abbr={g.away} color={teamColors[g.away]} />
            </span>
            <span className="text-center font-mono font-bold tabular-nums">
              {g.awayScore}–{g.homeScore}
            </span>
            <span className="font-semibold">
              <TeamTag abbr={g.home} color={teamColors[g.home]} />
            </span>
            <span className="text-right font-mono text-xs tabular-nums text-muted-foreground">
              {(100 * g.pHome).toFixed(0)}%
            </span>
            <span className="flex items-center justify-end gap-1 font-mono text-xs font-bold">
              {g.pick}
              {g.correct ? (
                <Check className="size-3.5 text-chart-3" />
              ) : (
                <X className="size-3.5 text-live" />
              )}
            </span>
          </div>
        ))}
      </div>

      {shown.length < filtered.length && (
        <button
          onClick={() => setLimit((l) => l + 50)}
          className="mt-4 flex w-full items-center justify-center gap-1 rounded-xl bg-secondary py-2.5 text-xs font-semibold text-muted-foreground transition-colors hover:text-foreground"
        >
          Show more <ChevronDown className="size-3.5" />
        </button>
      )}
    </div>
  )
}

function TeamTag({ abbr, color }: { abbr: string; color?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="size-2 rounded-full"
        style={{ background: color ?? "var(--muted-foreground)" }}
      />
      {abbr}
    </span>
  )
}
