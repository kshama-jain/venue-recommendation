# Academic Venue Recommendation System

A web application for discovering and recommending academic conferences and journals with real-time CFP (Call for Papers) tracking.

## Project Structure

```
e:\journal\
├── backend/              # Flask backend server
│   └── server.py        # Main backend API server
├── frontend/            # React frontend application
│   ├── public/          # Static assets and CSV data
│   └── src/             # React components
├── data/                # Data scripts and CSV files
│   ├── conference_live.py      # Live conference CFP fetcher
│   ├── realtime_worker.py      # Real-time CFP discovery hunter
│   └── live_open_cfps.csv      # Output CSV with live CFPs
└── others/              # Additional scripts
    └── live_cfp_worker.py      # Comprehensive CFP scraper worker
```

## Prerequisites

- Python 3.12+
- Node.js 18+
- Required Python packages:
  ```
  pip install flask requests beautifulsoup4 pyyaml python-dateutil transformers torch torchvision
  ```
- Required Node packages (install in frontend/):
  ```
  npm install
  ```

## Starting the Services

### 1. Start the Live Conference Data Fetcher

This script fetches live CFP data from HuggingFace AI Deadlines and PapersWithCode.

```bash
cd e:\journal\data
python conference_live.py
```

This will:
- Fetch live CFPs from AI deadline sources
- Save to `data/live_open_cfps.csv`
- Copy to `frontend/public/live_open_cfps.csv`
- Run once and exit

### 2. Start the Real-Time CFP Hunter

This script continuously hunts for new CFPs using OpenAlex, Crossref APIs, and WikiCFP scraping.

```bash
cd e:\journal\data
python realtime_worker.py
```

This will:
- Query OpenAlex and Crossref APIs for new sources
- Scrape WikiCFP for recent conference listings
- Only save entries with future deadlines
- Sleep 24 hours if no new entries found
- Sleep 1 hour if new entries were found

**Note:** Run this in a separate terminal/PowerShell window to keep it running continuously.

### 3. Start the Comprehensive CFP Worker (Optional)

This is the main worker that scrapes multiple sources (HuggingFace, PapersWithCode, IEEE, ACM, publishers).

```bash
cd e:\journal\others
python live_cfp_worker.py
```

This will:
- Scrape from multiple CFP sources
- Run in a forever loop (auto-restart on crash)
- Refresh every 60 minutes
- Save to both `data/live_open_cfps.csv` and `frontend/public/live_open_cfps.csv`

**Note:** This is a more comprehensive scraper but may take longer to run.

### 4. Start the Backend Server

The Flask backend serves the API and loads the CSV data.

```bash
cd e:\journal\backend
python server.py
```

The backend will:
- Start on `http://127.0.0.1:5000`
- Load live CFPs from `data/live_open_cfps.csv`
- Load rolling journals from `data/rolling_journals.csv`
- Serve recommendation endpoints

### 5. Start the Frontend

The React frontend serves the user interface.

```bash
cd e:\journal\frontend
npm start
```

The frontend will:
- Start on `http://localhost:3000`
- Fetch data from the backend API
- Display conferences, journals, and recommendations

## Recommended Startup Order

For a complete system running with real-time data:

1. **Terminal 1:** Start `realtime_worker.py` (continuous CFP hunting)
   ```bash
   cd e:\journal\data
   python realtime_worker.py
   ```

2. **Terminal 2:** Start `live_cfp_worker.py` (comprehensive scraping)
   ```bash
   cd e:\journal\others
   python live_cfp_worker.py
   ```

3. **Terminal 3:** Start the backend server
   ```bash
   cd e:\journal\backend
   python server.py
   ```

4. **Terminal 4:** Start the frontend
   ```bash
   cd e:\journal\frontend
   npm start
   ```

## Quick Start (Minimal)

If you just want to test the application with existing data:

1. Start backend:
   ```bash
   cd e:\journal\backend
   python server.py
   ```

2. Start frontend:
   ```bash
   cd e:\journal\frontend
   npm start
   ```

The application will use the existing `live_open_cfps.csv` file.

## Data Files

- `data/live_open_cfps.csv` - Live conference CFP data (updated by workers)
- `data/rolling_journals.csv` - Rolling journal data
- `frontend/public/live_open_cfps.csv` - Copy of live CFPs for frontend access

## API Endpoints

- `GET /api/venues` - Get all venues (conferences + journals)
- `GET /api/conferences` - Get conferences only
- `GET /api/journals` - Get journals only
- `POST /api/recommend` - Get venue recommendations
- `GET /api/live-cfps` - Get live CFP data

## Troubleshooting

### Backend not loading CSV data
- Ensure `data/live_open_cfps.csv` exists
- Run `conference_live.py` or `live_cfp_worker.py` to generate it

### Frontend not connecting to backend
- Ensure backend is running on `http://127.0.0.1:5000`
- Check CORS settings in `backend/server.py`

### Real-time worker not finding new entries
- This is normal if no new CFPs have been posted
- The worker will sleep and retry automatically
- Check internet connection

### Worker scripts timing out
- Some sources (WikiCFP, CFPList) may timeout due to network issues
- The workers will continue with other sources
- Disabled sources are commented out in the code

## Notes

- The `realtime_worker.py` is designed to run forever and automatically sleeps based on results
- The `live_cfp_worker.py` also runs forever with 60-minute refresh cycles
- Both workers can run simultaneously in different terminals
- The backend automatically reloads CSV data on restart
- The frontend fetches fresh data from the backend on each request
