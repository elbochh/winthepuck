"use client"

import { motion } from "framer-motion"
import { ArrowRight, Activity, Target, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { RinkBackground } from "@/components/rink-background"
import type { HeroStats } from "@/lib/data"

export function Hero({ stats }: { stats: HeroStats }) {
  const cards = [
    {
      label: `Confident-pick accuracy (${stats.confidentGames} picks)`,
      value: `${stats.confidentAccuracy}%`,
      icon: Target,
    },
    {
      label: "Games in training data",
      value: stats.gamesTracked.toLocaleString(),
      icon: Activity,
    },
    {
      label: "Live updates / game",
      value: `${stats.liveUpdatesPerGame}+`,
      icon: TrendingUp,
    },
  ]

  return (
    <section
      id="top"
      className="relative flex min-h-[100svh] items-center justify-center overflow-hidden px-4 pt-28 pb-16"
    >
      <RinkBackground />

      <div className="relative z-10 mx-auto flex max-w-4xl flex-col items-center text-center">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="glass mb-6 flex items-center gap-2 rounded-full border border-border px-4 py-1.5 text-xs font-medium text-muted-foreground"
        >
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-live opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-live" />
          </span>
          Live win probability • powered by play-by-play data
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          className="text-balance text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl"
        >
          Predict every shift before the{" "}
          <span className="bg-gradient-to-r from-primary via-primary to-chart-3 bg-clip-text text-transparent">
            puck drops
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.12 }}
          className="mt-5 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg"
        >
          IceEdge blends advanced team metrics with real-time game events to
          give you pre-game predictions and win probabilities that shift live
          with every goal, power play, and save. Every number below comes from
          real out-of-sample tests on {stats.predictedGames.toLocaleString()}{" "}
          NHL games.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.18 }}
          className="mt-8 flex flex-col gap-3 sm:flex-row"
        >
          <Button
            size="lg"
            className="group rounded-xl font-semibold"
            render={<a href="/season" />}
          >
            2025–26 season review
            <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
          </Button>
          <Button
            size="lg"
            variant="secondary"
            className="rounded-xl font-semibold"
            render={<a href="#live" />}
          >
            Watch a live game
          </Button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.26 }}
          className="mt-12 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3"
        >
          {cards.map((s) => (
            <div
              key={s.label}
              className="glass flex items-center gap-3 rounded-2xl border border-border px-4 py-3 text-left"
            >
              <span className="flex size-9 items-center justify-center rounded-xl bg-primary/15 text-primary">
                <s.icon className="size-4.5" />
              </span>
              <div>
                <div className="text-lg font-bold leading-none">{s.value}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {s.label}
                </div>
              </div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
