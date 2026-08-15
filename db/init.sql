-- =============================================================================
-- NFL BetMaster — Database Schema (PostgreSQL 16)
-- =============================================================================

-- ─── ENUMS ──────────────────────────────────────────────────────────────────

CREATE TYPE game_status AS ENUM ('pre', 'in_progress', 'post');
CREATE TYPE bet_type    AS ENUM ('moneyline', 'spread', 'over_under', 'prop', 'parlay');
CREATE TYPE bet_result  AS ENUM ('pending', 'won', 'lost', 'push', 'void');

-- ─── TEAMS ──────────────────────────────────────────────────────────────────

CREATE TABLE teams (
    id            SERIAL PRIMARY KEY,
    espn_id       VARCHAR(10) UNIQUE NOT NULL,
    abbreviation  VARCHAR(5)  NOT NULL,
    name          VARCHAR(60) NOT NULL,
    conference    VARCHAR(3)  NOT NULL,  -- AFC / NFC
    division      VARCHAR(10) NOT NULL,  -- North / South / East / West
    logo_url      TEXT,
    primary_color VARCHAR(7),            -- hex color e.g. #002244
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── GAMES ──────────────────────────────────────────────────────────────────

CREATE TABLE games (
    id                  SERIAL PRIMARY KEY,
    espn_event_id       VARCHAR(20) UNIQUE NOT NULL,
    season              SMALLINT    NOT NULL,
    week                SMALLINT    NOT NULL,
    game_type           VARCHAR(20) DEFAULT 'regular',   -- regular, wildcard, divisional, conference, superbowl
    status              game_status DEFAULT 'pre',
    home_team_id        INT REFERENCES teams(id),
    away_team_id        INT REFERENCES teams(id),
    home_score          INT DEFAULT 0,
    away_score          INT DEFAULT 0,
    quarter             SMALLINT,                        -- 1-4, 5 = OT
    clock               VARCHAR(10),                     -- "12:34"
    possession_team_id  INT REFERENCES teams(id),
    down                SMALLINT,                        -- 1-4
    distance            SMALLINT,                        -- yards to go
    yard_line           SMALLINT,                        -- 0-100
    yard_line_territory VARCHAR(5),                      -- team abbreviation
    start_time          TIMESTAMPTZ,
    venue               VARCHAR(120),
    broadcast           VARCHAR(60),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_games_espn_event    ON games(espn_event_id);
CREATE INDEX idx_games_season_week   ON games(season, week);
CREATE INDEX idx_games_status        ON games(status);

-- ─── ODDS (historical snapshots) ───────────────────────────────────────────

CREATE TABLE odds (
    id                SERIAL PRIMARY KEY,
    game_id           INT REFERENCES games(id) ON DELETE CASCADE,
    sportsbook        VARCHAR(60)  NOT NULL,
    home_moneyline    INT,                              -- e.g. -150
    away_moneyline    INT,                              -- e.g. +130
    spread            NUMERIC(4,1),                     -- e.g. -3.5
    spread_odds_home  INT,                              -- e.g. -110
    spread_odds_away  INT,                              -- e.g. -110
    over_under        NUMERIC(4,1),                     -- e.g. 47.5
    over_odds         INT,                              -- e.g. -110
    under_odds        INT,                              -- e.g. -110
    captured_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_odds_game_captured ON odds(game_id, captured_at DESC);

-- ─── USER BETS (personal tracker) ──────────────────────────────────────────

CREATE TABLE user_bets (
    id                SERIAL PRIMARY KEY,
    game_id           INT REFERENCES games(id) ON DELETE SET NULL,
    bet_type          bet_type     NOT NULL,
    pick              VARCHAR(120) NOT NULL,             -- e.g. "KC Chiefs -3.5"
    odds_decimal      NUMERIC(6,3) NOT NULL,             -- e.g. 1.909
    odds_american     INT,                               -- e.g. -110
    stake             NUMERIC(10,2) NOT NULL DEFAULT 0,
    potential_payout  NUMERIC(10,2) GENERATED ALWAYS AS (stake * odds_decimal) STORED,
    result            bet_result   DEFAULT 'pending',
    profit            NUMERIC(10,2) DEFAULT 0,           -- set on resolution
    notes             TEXT,
    created_at        TIMESTAMPTZ  DEFAULT NOW(),
    resolved_at       TIMESTAMPTZ
);

CREATE INDEX idx_bets_result   ON user_bets(result);
CREATE INDEX idx_bets_created  ON user_bets(created_at DESC);

-- ─── SEED: 32 NFL TEAMS ────────────────────────────────────────────────────

INSERT INTO teams (espn_id, abbreviation, name, conference, division, primary_color, logo_url) VALUES
-- AFC East
('2',  'BUF', 'Buffalo Bills',        'AFC', 'East',  '#00338D', 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png'),
('15', 'MIA', 'Miami Dolphins',       'AFC', 'East',  '#008E97', 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png'),
('17', 'NE',  'New England Patriots', 'AFC', 'East',  '#002244', 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png'),
('20', 'NYJ', 'New York Jets',        'AFC', 'East',  '#125740', 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png'),
-- AFC North
('33', 'BAL', 'Baltimore Ravens',     'AFC', 'North', '#241773', 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png'),
('4',  'CIN', 'Cincinnati Bengals',   'AFC', 'North', '#FB4F14', 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png'),
('5',  'CLE', 'Cleveland Browns',     'AFC', 'North', '#311D00', 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png'),
('23', 'PIT', 'Pittsburgh Steelers',  'AFC', 'North', '#FFB612', 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png'),
-- AFC South
('34', 'HOU', 'Houston Texans',       'AFC', 'South', '#03202F', 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png'),
('11', 'IND', 'Indianapolis Colts',   'AFC', 'South', '#002C5F', 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png'),
('30', 'JAX', 'Jacksonville Jaguars', 'AFC', 'South', '#006778', 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png'),
('10', 'TEN', 'Tennessee Titans',     'AFC', 'South', '#0C2340', 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png'),
-- AFC West
('7',  'DEN', 'Denver Broncos',       'AFC', 'West',  '#FB4F14', 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png'),
('12', 'KC',  'Kansas City Chiefs',   'AFC', 'West',  '#E31837', 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png'),
('13', 'LV',  'Las Vegas Raiders',    'AFC', 'West',  '#000000', 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png'),
('24', 'LAC', 'Los Angeles Chargers', 'AFC', 'West',  '#0080C6', 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png'),
-- NFC East
('6',  'DAL', 'Dallas Cowboys',       'NFC', 'East',  '#003594', 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png'),
('19', 'NYG', 'New York Giants',      'NFC', 'East',  '#0B2265', 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png'),
('21', 'PHI', 'Philadelphia Eagles',  'NFC', 'East',  '#004C54', 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png'),
('28', 'WSH', 'Washington Commanders','NFC', 'East',  '#5A1414', 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png'),
-- NFC North
('3',  'CHI', 'Chicago Bears',        'NFC', 'North', '#0B162A', 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png'),
('8',  'DET', 'Detroit Lions',        'NFC', 'North', '#0076B6', 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png'),
('9',  'GB',  'Green Bay Packers',    'NFC', 'North', '#203731', 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png'),
('16', 'MIN', 'Minnesota Vikings',    'NFC', 'North', '#4F2683', 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png'),
-- NFC South
('1',  'ATL', 'Atlanta Falcons',      'NFC', 'South', '#A71930', 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png'),
('29', 'CAR', 'Carolina Panthers',    'NFC', 'South', '#0085CA', 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png'),
('18', 'NO',  'New Orleans Saints',   'NFC', 'South', '#D3BC8D', 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png'),
('27', 'TB',  'Tampa Bay Buccaneers', 'NFC', 'South', '#D50A0A', 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png'),
-- NFC West
('22', 'ARI', 'Arizona Cardinals',    'NFC', 'West',  '#97233F', 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png'),
('14', 'LAR', 'Los Angeles Rams',     'NFC', 'West',  '#003594', 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png'),
('25', 'SF',  'San Francisco 49ers',  'NFC', 'West',  '#AA0000', 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png'),
('26', 'SEA', 'Seattle Seahawks',     'NFC', 'West',  '#002244', 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png');
