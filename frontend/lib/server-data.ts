// Server-side data access. Reads the JSON exported by
// ../ml/export_site_data.py from the local `data/` directory.
//
// CLOUD NOTE (Azure phase): this module is the single seam between the site
// and its data. When the class moves to Azure, replace the `readJson` calls
// with fetches against the deployed API (e.g. Azure Functions + Blob/SQL),
// nothing else in the app needs to change. The /api route handlers already
// expose these payloads over HTTP with the shapes the frontend consumes.

import { cache } from "react"
import { promises as fs } from "fs"
import path from "path"
import type {
  Game,
  HeroStats,
  LiveDemo,
  ModelEntry,
  SeasonData,
  Team,
  TeamStats,
} from "@/lib/data"

const DATA_DIR = path.join(process.cwd(), "data")

async function readJson<T>(name: string): Promise<T> {
  const raw = await fs.readFile(path.join(DATA_DIR, name), "utf8")
  return JSON.parse(raw) as T
}

type TeamJson = {
  abbr: string
  name: string
  city: string
  color: string
  record: string
  points: number
  pointsPct: number
  streak: string
  gamesPlayed: number
  stats: Partial<Omit<TeamStats, "form">>
  form: ("W" | "L" | "O")[]
}

type UpcomingJson = {
  id: number
  startsAt: string
  home: string
  away: string
  pHome: number
  confidence: number
  homeOdds: number
  awayOdds: number
  pick: string
}

export const getTeams = cache(async (): Promise<Record<string, TeamJson>> => {
  return readJson<Record<string, TeamJson>>("teams.json")
})

export const getHeroStats = cache(async (): Promise<HeroStats> => {
  return readJson<HeroStats>("hero.json")
})

export const getSeason = cache(async (): Promise<SeasonData> => {
  return readJson<SeasonData>("season.json")
})

export const getModelLeaderboard = cache(async (): Promise<ModelEntry[]> => {
  return readJson<ModelEntry[]>("model_leaderboard.json")
})

export const getLiveDemo = cache(async (): Promise<LiveDemo> => {
  return readJson<LiveDemo>("live_demo.json")
})

function toTeam(t: TeamJson): Team {
  return {
    id: t.abbr.toLowerCase(),
    abbr: t.abbr,
    name: t.name,
    city: t.city,
    color: t.color,
    record: t.record,
    logoSeed: t.abbr.toLowerCase(),
  }
}

function toStats(t: TeamJson): TeamStats {
  return {
    goalsFor: t.stats.goalsFor ?? 0,
    goalsAgainst: t.stats.goalsAgainst ?? 0,
    powerPlay: t.stats.powerPlay ?? 0,
    penaltyKill: t.stats.penaltyKill ?? 0,
    shotsPerGame: t.stats.shotsPerGame ?? 0,
    faceoffWin: t.stats.faceoffWin ?? 0,
    form: t.form,
  }
}

export function buildTeam(teams: Record<string, TeamJson>, abbr: string): Team {
  const t = teams[abbr]
  if (!t) {
    return {
      id: abbr.toLowerCase(),
      abbr,
      name: abbr,
      city: "",
      color: "#64748b",
      record: "",
      logoSeed: abbr.toLowerCase(),
    }
  }
  return toTeam(t)
}

/**
 * Featured games shown on the home page.
 * In-season: upcoming games with model predictions.
 * Offseason: the final playoff series games, shown with the model's pregame
 * prediction AND the actual result so every number stays verifiable.
 */
export const getFeaturedGames = cache(async (): Promise<{
  games: Game[]
  offseason: boolean
}> => {
  const teams = await getTeams()
  const upcoming = await readJson<UpcomingJson[]>("upcoming.json")

  if (upcoming.length > 0) {
    const games = upcoming.slice(0, 4).map((u) => ({
      id: String(u.id),
      startsAt: u.startsAt,
      home: buildTeam(teams, u.home),
      away: buildTeam(teams, u.away),
      homeWinProb: Math.round(u.pHome * 100),
      confidence: Math.round(u.confidence * 100),
      homeOdds: u.homeOdds,
      awayOdds: u.awayOdds,
      homeStats: teams[u.home] ? toStats(teams[u.home]) : emptyStats(),
      awayStats: teams[u.away] ? toStats(teams[u.away]) : emptyStats(),
    }))
    return { games, offseason: false }
  }

  // offseason: last 4 playoff games, prediction vs actual result
  const season = await getSeason()
  const playoffGames = season.games.filter((g) => g.playoff).slice(-4)
  const games = playoffGames.map((g) => {
    const p = g.pHome
    return {
      id: String(g.id),
      startsAt: `${g.date}T00:00:00Z`,
      home: buildTeam(teams, g.home),
      away: buildTeam(teams, g.away),
      homeWinProb: Math.round(p * 100),
      confidence: Math.round(Math.max(p, 1 - p) * 100),
      homeOdds: fairOdds(p),
      awayOdds: fairOdds(1 - p),
      homeStats: teams[g.home] ? toStats(teams[g.home]) : emptyStats(),
      awayStats: teams[g.away] ? toStats(teams[g.away]) : emptyStats(),
      result: {
        homeScore: g.homeScore,
        awayScore: g.awayScore,
        winnerAbbr: g.winner,
        modelCorrect: g.correct,
      },
    }
  })
  return { games: games.reverse(), offseason: true }
})

function fairOdds(p: number): number {
  const q = Math.min(Math.max(p, 0.01), 0.99)
  return q >= 0.5
    ? Math.round(-100 * (q / (1 - q)))
    : Math.round(100 * ((1 - q) / q))
}

function emptyStats(): TeamStats {
  return {
    goalsFor: 0,
    goalsAgainst: 0,
    powerPlay: 0,
    penaltyKill: 0,
    shotsPerGame: 0,
    faceoffWin: 0,
    form: [],
  }
}
