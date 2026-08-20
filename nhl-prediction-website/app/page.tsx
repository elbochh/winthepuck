import { SiteNav } from "@/components/site-nav"
import { Hero } from "@/components/hero"
import { LiveGameSection } from "@/components/live-game"
import { UpcomingGames } from "@/components/upcoming-games"
import { MatchupComparison } from "@/components/matchup-comparison"
import { Leaderboard } from "@/components/leaderboard"
import { Discussion } from "@/components/discussion"
import { SiteFooter } from "@/components/site-footer"
import {
  getFeaturedGames,
  getHeroStats,
  getLiveDemo,
  getModelLeaderboard,
  getTeams,
  buildTeam,
} from "@/lib/server-data"

export default async function Page() {
  const [heroStats, featured, leaderboard, demo, teams] = await Promise.all([
    getHeroStats(),
    getFeaturedGames(),
    getModelLeaderboard(),
    getLiveDemo(),
    getTeams(),
  ])

  const demoHome = buildTeam(teams, demo.home)
  const demoAway = buildTeam(teams, demo.away)

  return (
    <main className="relative min-h-screen">
      <SiteNav />
      <Hero stats={heroStats} />
      <LiveGameSection demo={demo} home={demoHome} away={demoAway} />
      <UpcomingGames games={featured.games} offseason={featured.offseason} />
      <MatchupComparison games={featured.games} />
      <Leaderboard entries={leaderboard} />
      {featured.games[0] && <Discussion game={featured.games[0]} />}
      <SiteFooter />
    </main>
  )
}
