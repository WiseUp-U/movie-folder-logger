import sqlite3
from main import load_movies as load_json_movies
from database import load_movies as load_sqlite_movies

def migrate_database(db_path="movies.db"):
    with sqlite3.connect(db_path) as connection:
        connection.execute("BEGIN")
        current_version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        if current_version == 1:
            print("Database schema is already up to date.")
            return
        if current_version != 0:
            raise ValueError(
                f"Unsupported database version: {current_version}"
            )
        
        expected_columns = [
            "file_path",
            "title",
            "year",
            "filename",
            "selected_tmdb_id",
            "status",
            "error",
            "candidates"
        ]
        table_exists = connection.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'movies'
        """).fetchone() is not None

        if not table_exists:
            raise ValueError("Movies table does not exist.")
        columns = connection.execute(
            "PRAGMA table_info(movies)"
        ).fetchall()

        column_names = [column[1] for column in columns]
        if column_names != expected_columns:
            raise ValueError(
                f"Unexpected database columns: {column_names}"
            )
        expected_types = [
            "TEXT",
            "TEXT",
            "INTEGER",
            "TEXT",
            "INTEGER",
            "TEXT",
            "TEXT",
            "TEXT"
        ]

        column_types = [column[2].upper() for column in columns]

        if column_types != expected_types:
            raise ValueError(
                f"Unexpected database column types: {column_types}"
            )
        
        connection.execute("""
            CREATE TABLE movies_new (
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
        connection.execute("""
            INSERT INTO movies_new (
                file_path,
                title,
                year,
                filename,
                selected_tmdb_id,
                status,
                error,
                candidates
            )
            SELECT
                file_path,
                title,
                year,
                filename,
                selected_tmdb_id,
                status,
                error,
                candidates
                FROM movies
        """)
        old_count = connection.execute(
            "SELECT COUNT(*) FROM movies"
        ).fetchone()[0]

        new_count = connection.execute(
            "SELECT COUNT(*) FROM movies_new"
        ).fetchone()[0]

        if old_count != new_count:
            raise ValueError("Record count mismatch during migration")
        connection.execute("DROP TABLE movies")

        connection.execute("""
            ALTER TABLE movies_new RENAME TO movies
        """)

        connection.execute("PRAGMA user_version = 1")

def verify_json_migration():

    json_movies = load_json_movies("movies.json")
    sqlite_movies = load_sqlite_movies("movies.db")

    print("JSON records:", len(json_movies))
    print("SQLite records:", len(sqlite_movies))

    assert len(json_movies) == len(sqlite_movies)

    for json_movie in json_movies:
        sqlite_movie = next(
            movie for movie in sqlite_movies
            if movie["file_path"] == json_movie["file_path"]
        )

        assert json_movie == sqlite_movie

    print("Migration verified successfully!")

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python migrate.py [schema|verify]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "schema":
        migrate_database()
        print("Database schema migration completed!")

    elif command == "verify":
        verify_json_migration()

    else:
        print("Unknown command")
        sys.exit(1)
