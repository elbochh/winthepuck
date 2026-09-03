// Shared types + formatting helpers. All data now comes from real model
// exports (see lib/server-data.ts). No mock data lives here anymore.

export type Team = {
  id: string
  name: string
  city: string
  abbr: string
  color: string // hex accent for the team
  record: string // W-L-OTL
  logoSeed: string
}

export type TeamStats = {
  goalsFor: number
  goalsAgainst: number
  powerPlay: number // %
  penaltyKill: number // %
  shotsPerGame: number
  faceoffWin: number // %
  form: ("W" | "L" | "O")[] // last 5
}

export type GameResult = {
  homeScore: number
  awayScore: number
  winnerAbbr: string
  modelCorrect: boolean
}

export type Game = {
  id: string
  startsAt: string // ISO
  home: Team
  away: Team
  homeWinProb: number // 0-100 pre-game
  confidence: number // 0-100 model confidence
  homeOdds: number // model fair odds, american
  awayOdds: number
  homeStats: TeamStats
  awayStats: TeamStats
  result?: GameResult // present when the game has been played
}

export type LiveEvent = {
  minute: number
  label: string
  team: "home" | "away" | "neutral"
  homeProb: number // win prob after this event (0-100)
}

export type LiveDemo = {
  gameId: number
  date: string
  label: string
  home: string
  away: string
  finalHome: number
  finalAway: number
  pregameHomeProb: number
  timeline: (LiveEvent & {
    period: number
    clock: string
    homeScore: number
    awayScore: number
  })[]
}

export type ModelEntry = {
  rank: number
  model: string
  accuracy: number // %
  logLoss: number
  correctPicks: number
  games: number
  bestStreak: number
}

export type HeroStats = {
  confidentAccuracy: number
  confidentGames: number
  gamesTracked: number
  predictedGames: number
  liveUpdatesPerGame: number
  seasonAccuracy: number
}

export type SeasonGame = {
  id: number
  date: string
  home: string
  away: string
  homeScore: number
  awayScore: number
  pHome: number
  pick: string
  winner: string
  correct: boolean
  playoff: boolean
}

export type SeasonData = {
  season: string
  summary: {
    games: number
    accuracy: number
    highConfidenceAccuracy: number
    highConfidenceGames: number
    logLoss: number
  }
  monthly: { month: string; n: number; accuracy: number }[]
  confidenceBuckets: { range: string; n: number; accuracy: number }[]
  games: SeasonGame[]
}

export type Comment = {
  id: string
  user: string
  avatarSeed: string
  time: string
  text: string
  likes: number
  pick: "home" | "away"
}

export function formatTipoff(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export function formatOdds(o: number) {
  return o > 0 ? `+${o}` : `${o}`
}

// Seeded discussion demo for the community feature, not model output.
export const comments: Comment[] = [
  {
    id: "c1",
    user: "SlapshotSam",
    avatarSeed: "sam",
    time: "12m",
    text: "Model had the Avs all series. Elo margin adjustment earns its keep in the playoffs.",
    likes: 34,
    pick: "home",
  },
  {
    id: "c2",
    user: "IceColdAnalytics",
    avatarSeed: "ice",
    time: "27m",
    text: "The live win-prob swings on penalties are so satisfying to watch in the replay.",
    likes: 21,
    pick: "home",
  },
  {
    id: "c3",
    user: "PuckLuck99",
    avatarSeed: "puck",
    time: "44m",
    text: "60%+ on confident picks over a full season is legit. Vegas closing lines hover around 59.",
    likes: 12,
    pick: "away",
  },
  {
    id: "c4",
    user: "BlueLineBetty",
    avatarSeed: "betty",
    time: "1h",
    text: "Check the season review page. December was rough but the model recovered.",
    likes: 47,
    pick: "away",
  },
]
