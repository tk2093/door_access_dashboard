# ASC Door Access Dashboard

An interactive dashboard to monitor and analyze door access using the OpenPath API.

## Features

- **Real-time Dashboard** - See today's, this week's, and this month's access statistics
- **Access Logs** - Searchable, filterable table of all door access events
- **User Management** - View all users and their access history
- **Door Analytics** - See which doors are most used
- **Charts & Trends** - Visualize access patterns by hour, day of week, and over time
- **CSV Export** - Export access logs for reporting
- **Auto-Sync** - Automatically syncs with OpenPath every 15 minutes

## Screenshots

The dashboard includes:
- Overview cards with key metrics
- Hourly and daily access charts
- Top doors and top users visualizations
- Detailed access log table with search/filter
- User detail modal with activity history

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   cd door_access_dash
   ```

2. **Create the `.env` file with your OpenPath credentials**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

   Your `.env` file should contain:
   ```
   OPENPATH_USERNAME=your_email@example.com
   OPENPATH_PASSWORD=your_password_here
   OPENPATH_ORG_ID=  # Leave empty to auto-detect
   DATABASE_URL=sqlite+aiosqlite:///./door_access.db
   SYNC_INTERVAL_MINUTES=15
   ```

3. **Install dependencies with uv**
   ```bash
   uv sync
   ```

4. **Run the application**
   ```bash
   uv run uvicorn backend.main:app --reload
   ```

5. **Open the dashboard**
   
   Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

6. **Initial Sync**
   
   Click the "Sync Now" button to pull data from OpenPath for the first time.

## Project Structure

```
door_access_dash/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration settings
│   ├── database.py          # SQLAlchemy models
│   ├── openpath_client.py   # OpenPath API client
│   ├── sync_service.py      # Data sync service
│   ├── migrate_to_postgres.py  # SQLite to PostgreSQL migration
│   └── routes/
│       ├── dashboard.py     # Dashboard API endpoints
│       └── sync.py          # Sync API endpoints
├── frontend/
│   ├── index.html           # Dashboard HTML
│   ├── css/styles.css       # Styling
│   └── js/dashboard.js      # Dashboard JavaScript
├── pyproject.toml           # Python dependencies (uv)
├── .env.example             # Environment template
└── README.md
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/stats` | Dashboard statistics |
| `GET /api/access-logs` | Paginated access logs |
| `GET /api/users` | List all users |
| `GET /api/users/{id}` | User detail with activity |
| `GET /api/doors` | List all doors |
| `GET /api/charts/hourly` | Hourly access distribution |
| `GET /api/charts/daily` | Daily access trend |
| `GET /api/charts/weekday` | Weekly pattern |
| `POST /api/sync/trigger` | Trigger manual sync |
| `GET /api/sync/status` | Check sync status |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OPENPATH_USERNAME` | - | Your OpenPath email |
| `OPENPATH_PASSWORD` | - | Your OpenPath password |
| `OPENPATH_ORG_ID` | Auto-detect | Organization ID |
| `DATABASE_URL` | `sqlite+aiosqlite:///./door_access.db` | Database connection |
| `SYNC_INTERVAL_MINUTES` | `15` | Auto-sync interval |

## Database Options

The app uses SQLAlchemy ORM, making it easy to switch databases. By default, it uses a local SQLite file, but you can use a cloud-hosted PostgreSQL database to access your data from anywhere.

### Option 1: Local SQLite (Default)

No setup required. Data is stored in `door_access.db` in the project root.

```
DATABASE_URL=sqlite+aiosqlite:///./door_access.db
```

### Option 2: Cloud PostgreSQL (Recommended for Portability)

Use a cloud-hosted PostgreSQL database to access your data from any machine.

#### Setting Up Neon (Free Tier)

1. Create a free account at [neon.tech](https://neon.tech)
2. Create a new project (e.g., "door-access")
3. Copy your connection string from the dashboard
4. Update your `.env` file:

```
DATABASE_URL=postgresql+asyncpg://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

**Other free PostgreSQL providers:**
- [Supabase](https://supabase.com) - 500MB free
- [Railway](https://railway.app) - $5 free credit
- [Render](https://render.com) - Free PostgreSQL (90-day limit)

#### Migrating Existing Data to PostgreSQL

If you have existing data in SQLite that you want to keep, use the migration script:

```bash
# Set your target PostgreSQL URL
export TARGET_DATABASE_URL="postgresql+asyncpg://user:pass@host/db?sslmode=require"

# Run the migration
uv run python -m backend.migrate_to_postgres

# Or pass the URL directly
uv run python -m backend.migrate_to_postgres "postgresql+asyncpg://user:pass@host/db?sslmode=require"
```

The script will:
1. Read all data from your local SQLite database
2. Create tables in PostgreSQL
3. Transfer all users, doors, access logs, and sync status
4. Verify the migration was successful

After migration, update your `.env` to use the PostgreSQL URL and restart the app.

### Other Databases

**MySQL:**
```
DATABASE_URL=mysql+aiomysql://user:pass@localhost/door_access
```

Note: You'll need to install the appropriate async driver (`aiomysql` for MySQL).

## Deployment

### Docker (Coming Soon)

A Dockerfile will be provided for easy containerized deployment.

### Manual Deployment

1. Set up a server (VPS, cloud VM, Raspberry Pi)
2. Install Python 3.11+ and uv
3. Clone the repo and configure `.env`
4. Run with a process manager like systemd or supervisor:

```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Security Notes

- Keep your `.env` file secure and never commit it to git
- The OpenPath credentials have full access to your organization's data
- Consider adding authentication to the dashboard for production use

## License

MIT License - feel free to use!

---