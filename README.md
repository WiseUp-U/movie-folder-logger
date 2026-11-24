
# Movie Folder Logger

A Python application that scans a local movie collection, identifies movies using The Movie Database (TMDB), stores movie information in SQLite, and exports selected movies to a Letterboxd-compatible CSV file.

## Features

- Recursively scan directories for movie files.
- Extract movie titles and release years from filenames.
- Search TMDB for matching movies.
- Automatically identify unique matches.
- Send uncertain matches for manual review.
- Store movie information in SQLite.
- Retry previously failed lookups.
- Generate a report of movies requiring review.
- Export selected movies to Letterboxd CSV.



## Requirements

- Python 3.12 (tested)
- An internet connection for TMDB searches
- A TMDB API Read Access Token

### Dependencies

This project currently uses only Python's standard library. No third-party packages need to be installed.

## Installation

1. Clone the repository:

   ```bash
   git clone <YOUR_GITHUB_REPOSITORY_URL>
   cd movie_logger
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

3. Activate it:

   **Linux / macOS:**

   ```bash
   source .venv/bin/activate
   ```

   **Windows:**

   ```powershell
   .venv\Scripts\activate
   ```


## TMDB Configuration

This application uses the TMDB API to search for movies.

1. Create a TMDB account and obtain an API Read Access Token.
2. Set the token as an environment variable.

**Linux / macOS:**

```bash
export TMDB_READ_ACCESS_TOKEN="your_token_here"
```

**Windows PowerShell:**

```powershell
$env:TMDB_READ_ACCESS_TOKEN="your_token_here"
```

Keep your token private. Never commit it to Git or include it directly in source code.



## Usage

Make sure your virtual environment is activated and your TMDB token is configured.

Run the application:

```bash
python main.py
```

When prompted, enter the path to your movie directory.

The application will:

1. Scan the directory recursively for supported movie files.
2. Extract movie titles and release years from filenames.
3. Search TMDB for possible matches.
4. Automatically select unique, confident matches.
5. Save uncertain matches for manual review.
6. Generate a review report.
7. Export selected movies to `letterboxd_import.csv`.



### Supported Video Formats

The application scans for the following file extensions:

- MKV (`.mkv`)
- MP4 (`.mp4`)
- AVI (`.avi`)
- MOV (`.mov`)
- WMV (`.wmv`)
- M4V (`.m4v`)
- WebM (`.webm`)

File extensions are matched without regard to letter case.

### Manual Review

When multiple possible matches are found, the application asks you to select the correct movie.

Enter the number corresponding to your preferred candidate.

Invalid selections are rejected and you can try again.

### Generated Files

| File | Purpose |
|---|---|
| `movies.db` | Main SQLite database |
| `review_report.txt` | Movies requiring manual review |
| `letterboxd_import.csv` | Selected movies for Letterboxd import |



## Running Tests

Run the complete test suite:

```bash
python -m unittest -v
```

The tests cover filename parsing, movie identification, database operations, error handling, manual review, crash recovery, and CSV export.



## Project Structure

```text
movie_logger/
├── main.py
├── database.py
├── migrate.py
├── tmdb.py
├── test_main.py
├── test_movies/
│   ├── Arrival (2016).mkv
│   ├── Inception (2010).mp4
│   └── Interstellar (2014).mkv
├── README.md
└── .gitignore
```

### Main Modules

- `main.py` — Movie scanning, filename parsing, identification, manual review, and CSV export.
- `database.py` — SQLite database initialization, saving, and loading.
- `migrate.py` — Database schema migrations.
- `tmdb.py` — TMDB API requests and retry handling.
- `test_main.py` — Automated unit and integration tests.
- `test_movies/` — Sample movie files used for testing.
