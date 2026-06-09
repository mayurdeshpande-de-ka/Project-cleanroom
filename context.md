# Project Clean Room — Form 20 Backlog Dashboard

## What This Is
Internal ops dashboard for tracking the **Form 20 extraction pipeline** — Form 20 is the ECI (Election Commission of India) official election result document published per AC (Assembly Constituency) for every election. The project extracts, processes, and pushes these results into a central RDS database.

---

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | Python / Flask |
| Primary DB | SQLite (local) or Turso (cloud SQLite) via `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` |
| Analytics DB | AWS RDS PostgreSQL (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) |
| Frontend | Vanilla JS + Tailwind CSS (CDN) + Chart.js |
| Entry point | `app.py` → runs on port 5050 |
| Launch config | `.claude/launch.json` → `python app.py` |

---

## Navigation Tabs
| Tab | Description |
|---|---|
| **Dashboard** | 4-card analytics grid (Form 20, Retro, Booth Data, Caste Data) |
| **Listing** | Pipeline table — records with pipeline strip + filter/search |
| **Retro Export** | Modal to export historical election results from RDS |
| **Weekly Report** | (formerly "Glance Report") Weekly push velocity, state performance, PDF export |

---

## Dashboard Cards

### Card 1: Form 20
Analytics of the Form 20 extraction pipeline (non-BP elections only).

- **Ring %** = Form 20 tracker entries / AC-PC mapping total entries (entry-level coverage)
- **Badge** = "X% coverage"
- **Subtitle** = "99 / 262 elections in Form 20"
- **Year strip** = Mapping years (19, from RDS `ac_election_mapping`) | In Form 20 (14, distinct years in SQLite) | Mapping Entries (262, state×year×type combos)
- **By Election Type** = AE and GE only (no BP). Denominator = mapping totals from RDS `mapping_by_type` (GE: 148, AE: 114). Numerator = pipeline-completed from SQLite. Shows pipeline_completed/mapping_total per type.
- **Top Completed States** = states ranked by db_pushed count
- Data source: `/api/stats?hide_bp=1` + `/api/dashboard/analytics` (mapping_years, mapping_entries)

### Card 2: Retro
AC-wise coverage of historical election results in RDS (non-BP only).

- **Ring %** = available ACs / total expected ACs
- **ACs in DB** = sum of (canonical AC count × elections with data per state)
- **Canonical AC count** = `COUNT(DISTINCT ac_no) FROM ac_mapping GROUP BY state_abb`
- **By type** = AE vs GE (no BP), shows AC-level coverage
- **Top States** = by available ACs with % completion
- Data source: `/api/dashboard/analytics` → RDS queries on `election_result`, `ac_election_mapping`, `ac_mapping`

### Card 3: Booth Data
Coverage of `booth_metadata` table in RDS (states, ACs, booths, voters).

### Card 4: Caste Data
Coverage of `caste_details` table in RDS.

---

## Listing Page
- **Pipeline strip**: Missing → Downloaded → Extracted → DB Pushed + progress %
- Each stage is clickable to filter the table
- Filters: state, election type, year, SIR only, Show BP
- Table views: States (grouped) → click state → election detail

---

## Key Data Rules
- **BP elections excluded** everywhere: `hide_bp=1` on stats, glance/weekly report, and all analytics queries use `POSITION('-BP' IN el_type) = 0`
- **Unique Entry** = (state, el_year, el_type) e.g. "MP 2019 GE = 1 entry"
- **AC count** = `COUNT(DISTINCT ac_no) FROM ac_mapping` per state (canonical; same per state regardless of year/type)
- **election_result.ac_no** is a globally-unique row identifier (NOT the constituency number); use `ac_mapping` for canonical AC counts
- **Retro metadata** is cached in `retro_metadata.json` and refreshed every 10 min
- **Analytics cache** is stored in `analytics_cache.json`, rebuilt every 10 min in background; fast-path returns 202 until ready

---

## Key API Endpoints
| Endpoint | Description |
|---|---|
| `GET /api/stats?hide_bp=1` | Pipeline stats, by_type, by_state, year breakdown |
| `GET /api/records` | All records with filters |
| `PATCH /api/records/<id>` | Update record status/remark/wip |
| `GET /api/dashboard/analytics` | Cached RDS analytics (retro, booth, caste, mapping_years, mapping_entries) |
| `GET /api/glance_report?hide_bp=1` | Weekly push velocity, state performance |
| `GET /api/glance_report/pdf?hide_bp=1` | Download Weekly Report PDF |
| `GET /api/retro/metadata` | Cached {state: {el_type: {year: count}}} from RDS |
| `GET /api/retro/export` | Export retro data as CSV/XLSX |
| `POST /api/sync-rds` | Sync Form 20 statuses from RDS |

---

## SQLite Schema (records table)
Key columns: `id`, `state`, `state_name`, `el_type`, `el_year`, `key` (STATE-TYPE-YEAR), `overall_status` (missing/downloaded/extracted/db_pushed/completed), `is_sir_state`, `wip`, `remark`, `assigned_to`, `last_updated`

## RDS Tables (PostgreSQL)
- `election_result` — candidate-level results (one row per candidate per AC per election)
- `election` — election metadata (el_id, el_year, el_type)
- `ac_election_mapping` — expected elections per state (state_abb, el_year, el_type)
- `ac_mapping` — canonical AC list per state (state_abb, ac_no)
- `booth_metadata` — booth-level data (state_abb, ac_no, booth details, voters)
- `caste_details` — caste data per AC

---

## Frontend Architecture
- Single-page app: `templates/index.html` + `static/app.js`
- Tab switching shows/hides view divs: `#dashboard-view`, `#listing-view`, `#glance-view`
- Sidebar (`#listing-view` only): pipeline stage filter links
- Module-level state: `allRecords`, `filters`, `_f20TotalYears`, `_f20Total`, `analyticsLoaded`
- Analytics auto-retry: when `/api/dashboard/analytics` returns 202, retries after 15s

---

## Important Naming
- App called **"Project Clean Room"** in the navbar (was "Form 20 Tracker")
- "Weekly Report" tab (was "Glance Report")
- `use_reloader=False` — must restart server to pick up Python changes
