
import sqlite3
import json

def initialize_database(db_path="movies.db"):
    with sqlite3.connect(db_path) as connection:
        table_exists = connection.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'movies'
        """).fetchone() is not None

        connection.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                file_path TEXT PRIMARY KEY NOT NULL,
                title TEXT NOT NULL,
                year INTEGER CHECK (
                    year IS NULL OR (
                        typeof(year) = 'integer'
                        AND year BETWEEN 1888 AND 2100
                    )
                ),
                filename TEXT,
                selected_tmdb_id INTEGER,
                status TEXT,
                error TEXT,
                candidates TEXT
            )
        """)
        if not table_exists:
            connection.execute("PRAGMA user_version = 1")

def save_movie(movie, db_path="movies.db"):
    candidates = movie.get("candidates")
    title = movie.get("title")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("Movie title must be a non-empty string.")
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            INSERT INTO movies (
                file_path,
                title,
                year,
                filename,
                selected_tmdb_id,
                status,
                error,
                candidates
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(file_path) DO UPDATE SET
                title = excluded.title,
                year = CASE
                    WHEN ? THEN excluded.year
                    ELSE movies.year
                END,
                filename = CASE
                    WHEN ? THEN excluded.filename
                    ELSE movies.filename
                END,
                selected_tmdb_id = CASE
                    WHEN ? THEN excluded.selected_tmdb_id
                    ELSE movies.selected_tmdb_id
                END,
                status = CASE
                    WHEN ? THEN excluded.status
                    ELSE movies.status
                END,
                error = CASE
                    WHEN ? THEN excluded.error
                    ELSE movies.error
                END,
                candidates = CASE
                    WHEN ? THEN excluded.candidates
                    ELSE movies.candidates
                END
        """, (
            movie.get("file_path"),
            movie.get("title"),
            movie.get("year"),
            movie.get("filename"),
            movie.get("selected_tmdb_id"),
            movie.get("status"),
            movie.get("error"),
            json.dumps(candidates, ensure_ascii=False)
            if candidates is not None else None,
            "year" in movie,
            "filename" in movie,
            "selected_tmdb_id" in movie,
            "status" in movie,
            "error" in movie,
            "candidates" in movie,
        ))

def load_movies(db_path="movies.db"):
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            "SELECT * FROM movies"
        ).fetchall()

    movies = []

    for row in rows:
        movie = dict(row)

        if movie["candidates"] is not None:
            movie["candidates"] = json.loads(movie["candidates"])
        else:
            movie.pop("candidates")

        for key in ("error", "selected_tmdb_id", "status"):
            if movie[key] is None:
                movie.pop(key)

        movies.append(movie)

    return movies

def get_movie_paths(db_path="movies.db"):
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT file_path FROM movies"
        ).fetchall()

    return {row[0] for row in rows}



def migrate_json_to_sqlite(
    json_path="movies.json",
    db_path="movies.db"
):
    with open(json_path, "r", encoding="utf-8") as file:
        movies = json.load(file)

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM movies"
        ).fetchone()[0]

    if count:
        raise RuntimeError(
            "Database is not empty. Migration cancelled."
        )

    for movie in movies:
        save_movie(movie, db_path)

    return len(movies)
