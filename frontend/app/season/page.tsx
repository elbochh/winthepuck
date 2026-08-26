import type { Metadata } from "next"
import { SiteNav } from "@/components/site-nav"
import { SiteFooter } from "@/components/site-footer"
import { SeasonReview } from "@/components/season-review"
import { getSeason, getTeams } from "@/lib/server-data"

export const metadata: Metadata = {
  title: "2025–26 Season Review · WinThePuck",
  description:
    "Every out-of-sample model prediction for the 2025–26 NHL season, compared with what actually happened.",
}

export default async function SeasonPage() {
  const [season, teams] = await Promise.all([getSeason(), getTeams()])
  const teamColors = Object.fromEntries(
    Object.values(teams).map((t) => [t.abbr, t.color]),
  )

  return (
    <main className="relative min-h-screen">
      <SiteNav />
      <SeasonReview season={season} teamColors={teamColors} />
      <SiteFooter />
    </main>
  )
}
