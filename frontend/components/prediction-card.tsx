"use client"

import { motion } from "framer-motion"
import { Check, X, Clock, TrendingUp } from "lucide-react"
import { TeamLogo } from "@/components/team-logo"
import { WinProbBar } from "@/components/win-prob-bar"
import { ConfidenceRing } from "@/components/confidence-ring"
import { FormPips } from "@/components/form-pips"
import { type Game, formatTipoff, formatOdds } from "@/lib/data"

export function PredictionCard({ game, index }: { game: Game; index: number }) {
  const favored = game.homeWinProb >= 50 ? game.home : game.away
  const edge =
    game.homeWinProb >= 50 ? game.homeWinProb : 100 - game.homeWinProb

  return (
    <motion.article
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.45, delay: index * 0.06 }}
      whileHover={{ y: -4 }}
      className="group glass flex flex-col rounded-2xl border border-border p-5 shadow-lg transition-shadow hover:shadow-2xl hover:ring-1 hover:ring-primary/40"
    >
      <div className="mb-4 flex items-center justify-between text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Clock className="size-3.5" />
          {game.result
            ? new Date(game.startsAt).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
                timeZone: "UTC",
              })
            : formatTipoff(game.startsAt)}
        </span>
        {game.result ? (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold ${
              game.result.modelCorrect
                ? "bg-chart-3/15 text-chart-3"
                : "bg-live/15 text-live"
            }`}
          >
            {game.result.modelCorrect ? (
              <Check className="size-3.5" />
            ) : (
              <X className="size-3.5" />
            )}
            {game.result.modelCorrect ? "Model was right" : "Model was wrong"}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 font-medium text-foreground">
            <TrendingUp className="size-3.5 text-primary" />
            Model edge {edge}%
          </span>
        )}
      </div>

      <div className="mb-5 flex items-center gap-4">
        <div className="flex flex-1 flex-col gap-3">
          <TeamSide
            team={game.home}
            odds={game.homeOdds}
            form={game.homeStats.form}
            highlight={favored.id === game.home.id}
          />
          <TeamSide
            team={game.away}
            odds={game.awayOdds}
            form={game.awayStats.form}
            highlight={favored.id === game.away.id}
          />
        </div>
        <div className="flex flex-col items-center gap-1 border-l border-border pl-4">
          <ConfidenceRing value={game.confidence} size={60} />
        </div>
      </div>

      <WinProbBar home={game.home} away={game.away} homeProb={game.homeWinProb} />

      <div className="mt-5 flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          Pick:{" "}
          <span className="font-semibold text-foreground">
            {favored.city} {favored.name}
          </span>
        </span>
        {game.result ? (
          <span className="font-mono text-sm font-bold tabular-nums">
            Final&nbsp;
            <span className="text-foreground">
              {game.away.abbr} {game.result.awayScore} – {game.result.homeScore}{" "}
              {game.home.abbr}
            </span>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">
            Fair odds shown, no bookmaker vig
          </span>
        )}
      </div>
    </motion.article>
  )
}

function TeamSide({
  team,
  odds,
  form,
  highlight,
}: {
  team: Game["home"]
  odds: number
  form: ("W" | "L" | "O")[]
  highlight: boolean
}) {
  return (
    <div
      className={`flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors ${
        highlight ? "bg-primary/10 ring-1 ring-primary/30" : ""
      }`}
    >
      <TeamLogo team={team} size={40} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-bold leading-tight">{team.name}</span>
          {highlight && (
            <span className="rounded bg-primary px-1.5 py-0.5 text-[9px] font-bold uppercase text-primary-foreground">
              Fav
            </span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{team.record}</span>
          <FormPips form={form} />
        </div>
      </div>
      <span className="font-mono text-sm font-semibold tabular-nums text-muted-foreground">
        {formatOdds(odds)}
      </span>
    </div>
  )
}
