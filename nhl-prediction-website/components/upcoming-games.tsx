"use client"

import { SectionHeading } from "@/components/section-heading"
import { PredictionCard } from "@/components/prediction-card"
import type { Game } from "@/lib/data"

export function UpcomingGames({
  games,
  offseason,
}: {
  games: Game[]
  offseason: boolean
}) {
  return (
    <section id="games" className="mx-auto w-full max-w-6xl px-4 py-16 sm:py-20">
      <SectionHeading
        eyebrow={offseason ? "Stanley Cup Final" : "Today's slate"}
        title={
          offseason
            ? "How the model called the Final"
            : "Upcoming games & predictions"
        }
        description={
          offseason
            ? "The NHL is in its offseason — no games are scheduled. Here is the model's pregame call for each Stanley Cup Final game, next to what actually happened."
            : "Every matchup comes with a model-generated win probability, fair odds, recent form, and a confidence score."
        }
      />

      {games.length === 0 ? (
        <div className="glass rounded-2xl border border-border p-10 text-center text-muted-foreground">
          No games available yet. Refresh the data pipeline to load the newest
          slate.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {games.map((g, i) => (
            <PredictionCard key={g.id} game={g} index={i} />
          ))}
        </div>
      )}
    </section>
  )
}
