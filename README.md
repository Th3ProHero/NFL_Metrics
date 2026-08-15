# NFL BetMaster 🏈

Self-hosted NFL analytics, odds tracking, and bet management platform.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env to add your ODDS_API_KEY (optional)

# 2. Build and start all services
docker-compose up --build -d

# 3. Access the dashboard
open http://localhost:4000
```

## Architecture

| Service    | Port  | Description                           |
|------------|-------|---------------------------------------|
| Frontend   | 4000  | Next.js dashboard (Tailwind CSS)     |
| Backend    | 8000  | FastAPI REST + SSE API               |
| PostgreSQL | 5440  | Data storage                          |

## Features

- **Live Scoreboard** — Real-time scores via SSE from ESPN
- **Odds Tracking** — Historical line movement from The Odds API
- **Analysis** — Odds vs. EPA/DVOA for +EV identification
- **Bet Tracker** — Personal bet log with ROI dashboard

## Data Sources

- [ESPN Scoreboard API](https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard) (free, no key needed)
- [The Odds API](https://the-odds-api.com) (free tier: 500 req/month)
- nfl_data_py for historical EPA data

## License

MIT — Free for personal use.
# NFL_Metrics
