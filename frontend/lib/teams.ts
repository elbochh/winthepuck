export type TeamMeta = {
  tri: string
  name: string
  color: string // accent color used for logos, dots, and stat bars
}

// 2025-26 playoff teams referenced by the schedule.
export const TEAMS: Record<string, TeamMeta> = {
  MTL: { tri: "MTL", name: "Montréal Canadiens", color: "#af1e2d" },
  BUF: { tri: "BUF", name: "Buffalo Sabres", color: "#1d4 e8b".replace(" ", "") },
  TBL: { tri: "TBL", name: "Tampa Bay Lightning", color: "#0a2885" },
  CAR: { tri: "CAR", name: "Carolina Hurricanes", color: "#cc0000" },
  VGK: { tri: "VGK", name: "Vegas Golden Knights", color: "#b4975a" },
  COL: { tri: "COL", name: "Colorado Avalanche", color: "#8b2942" },
  NSH: { tri: "NSH", name: "Nashville Predators", color: "#ffb81c" },
}

const FALLBACK_COLOR = "#64748b"

export function getTeam(tri: string): TeamMeta {
  return TEAMS[tri] ?? { tri, name: tri, color: FALLBACK_COLOR }
}

// Official NHL logo CDN. Swapping to a different logo source is a one-line change.
export function teamLogo(tri: string): string {
  return `https://assets.nhle.com/logos/nhl/svg/${tri}_light.svg`
}
