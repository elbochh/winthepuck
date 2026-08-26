"use client"

import { motion } from "framer-motion"
import { Trophy, Flame, Crown, Bot } from "lucide-react"
import { SectionHeading } from "@/components/section-heading"
import type { ModelEntry } from "@/lib/data"

function ModelAvatar({ name }: { name: string }) {
  const hue = (name.split("").reduce((a, c) => a + c.charCodeAt(0), 0) * 7) % 360
  return (
    <span
      className="flex size-9 items-center justify-center rounded-full text-white ring-1 ring-white/15"
      style={{
        background: `radial-gradient(120% 120% at 30% 20%, hsl(${hue} 70% 55%), hsl(${(hue + 40) % 360} 65% 35%))`,
      }}
      aria-hidden="true"
    >
      <Bot className="size-4" />
    </span>
  )
}

export function Leaderboard({ entries }: { entries: ModelEntry[] }) {
  const [first, second, third] = entries

  return (
    <section id="leaderboard" className="mx-auto w-full max-w-6xl px-4 py-16 sm:py-20">
      <SectionHeading
        eyebrow="Model benchmark"
        title="Model leaderboard"
        description={`Every model was tested the honest way: retrained monthly and asked to predict games it had never seen — ${entries[0]?.games.toLocaleString()} games across four seasons (2022–2026).`}
      />

      {/* podium */}
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        {[second, first, third].filter(Boolean).map((p, i) => {
          const isFirst = p.rank === 1
          return (
            <motion.div
              key={p.model}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: i * 0.08 }}
              className={`glass relative flex flex-col items-center rounded-2xl border p-5 text-center ${
                isFirst
                  ? "border-primary/40 ring-1 ring-primary/30 sm:-mt-4"
                  : "border-border"
              }`}
            >
              {isFirst && (
                <Crown className="absolute -top-3 size-7 text-chart-4 drop-shadow" />
              )}
              <ModelAvatar name={p.model} />
              <p className="mt-3 truncate font-bold">{p.model}</p>
              <p className="text-xs text-muted-foreground">Rank #{p.rank}</p>
              <div className="mt-3 flex w-full items-center justify-around border-t border-border pt-3 text-xs">
                <div>
                  <div className="font-mono text-base font-bold text-primary">
                    {p.accuracy}%
                  </div>
                  <div className="text-muted-foreground">accuracy</div>
                </div>
                <div>
                  <div className="font-mono text-base font-bold">
                    {p.logLoss}
                  </div>
                  <div className="text-muted-foreground">log loss</div>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* table */}
      <div className="glass overflow-hidden rounded-2xl border border-border">
        <div className="grid grid-cols-[40px_1fr_auto] items-center gap-3 border-b border-border px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground sm:grid-cols-[40px_1fr_90px_90px_100px_110px]">
          <span>#</span>
          <span>Model</span>
          <span className="hidden text-right sm:block">Accuracy</span>
          <span className="hidden text-right sm:block">Log loss</span>
          <span className="hidden text-right sm:block">Best streak</span>
          <span className="text-right">Correct picks</span>
        </div>
        {entries.map((p, i) => (
          <motion.div
            key={p.model}
            initial={{ opacity: 0, x: -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.3, delay: i * 0.04 }}
            className="grid grid-cols-[40px_1fr_auto] items-center gap-3 border-b border-border px-4 py-3 transition-colors last:border-0 hover:bg-secondary/50 sm:grid-cols-[40px_1fr_90px_90px_100px_110px]"
          >
            <span className="flex items-center gap-1 font-mono font-bold text-muted-foreground">
              {p.rank <= 3 ? (
                <Trophy
                  className={`size-4 ${p.rank === 1 ? "text-chart-4" : p.rank === 2 ? "text-muted-foreground" : "text-chart-2"}`}
                />
              ) : (
                p.rank
              )}
            </span>
            <div className="flex min-w-0 items-center gap-3">
              <ModelAvatar name={p.model} />
              <div className="min-w-0">
                <p className="truncate font-semibold">{p.model}</p>
                <p className="text-xs text-muted-foreground sm:hidden">
                  {p.accuracy}% · {p.correctPicks.toLocaleString()} correct
                </p>
              </div>
            </div>
            <span className="hidden text-right font-mono font-semibold text-primary sm:block">
              {p.accuracy}%
            </span>
            <span className="hidden text-right font-mono font-semibold sm:block">
              {p.logLoss}
            </span>
            <span className="hidden items-center justify-end gap-1 text-right font-mono font-semibold sm:flex">
              <Flame className="size-3.5 text-live" />
              {p.bestStreak}
            </span>
            <span className="text-right font-mono font-semibold">
              {p.correctPicks.toLocaleString()}
              <span className="text-muted-foreground"> / {p.games.toLocaleString()}</span>
            </span>
          </motion.div>
        ))}
      </div>
    </section>
  )
}
