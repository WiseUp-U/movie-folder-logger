import tempfile
import os
import json
import csv
import re
from pathlib import Path
import urllib.error
from tmdb import search_movie_with_retry

from tmdb import search_movie
from database import (
    initialize_database,
    save_movie,
    get_movie_paths,
)
from database import load_movies as load_database_movies

VIDEO_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".webm",
}

def find_movies_to_process(old_movies, new_movies, old_paths):
    new_unprocessed = [
        movie for movie in new_movies
        if movie["file_path"] not in old_paths
    ]

    failed_movies = [
        movie for movie in old_movies
        if movie.get("status") == "error"
    ]

    return new_unprocessed, failed_movies

def load_movies(input_file):
    if not os.path.exists(input_file):
        return []

    with open(input_file, "r", encoding="utf-8") as file:
        return json.load(file)

def export_letterboxd_csv(movies, output_file):
    with open(output_file, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["tmdbID", "Title", "Year"])
        for movie in movies:
            if movie.get("selected_tmdb_id") is not None:
                found = False
                for candidate in movie.get("candidates", []):
                    if candidate.get("tmdb_id") == movie["selected_tmdb_id"]:
                        title = candidate.get("title")
                        if not isinstance(title, str) or not title.strip():
                            continue

                        writer.writerow([
                            candidate["tmdb_id"],
                            title,
                            candidate.get("year")
                        ])

                        found = True
                        break
                if not found:
                    print(f"Warning: Selected candidate not found for {movie['title']}")

def review_movies(movies, db_path=None):
    for movie in movies:
        if movie.get("status") == "review":
            if not movie.get("candidates"):
                print(f"Warning: No candidates available for {movie['title']}. Skipping.")
                continue
            print(f"\n{movie['title']} ({movie['year'] or 'Unknown year'})")

            display_candidates(movie["candidates"])

            while True:
                selection = input("Please select a movie: ")

                try:
                    selected_candidate = select_candidate(
                        movie["candidates"],
                        selection
                    )
                except ValueError as error:
                    print(error)
                    continue

                original_movie = movie.copy()

                save_selection(movie, selected_candidate)

                try:
                    if db_path:
                        save_movie(movie, db_path)
                except Exception:
                    movie.clear()
                    movie.update(original_movie)
                    raise

                break

def generate_review_report(movies, output_file):
    with open(output_file, "w", encoding="utf-8") as file:
        counter = 1
        for movie in movies:
            if movie["status"] == "review":

                if movie["year"] is None:
                    file.write(f"{counter}. {movie['title']} (unknown year)\n")
                else:
                    file.write(f"{counter}. {movie['title']} ({movie['year']})\n")
                counter += 1
                for index, candidate in enumerate(movie.get("candidates", []), start=1):
                    file.write(
                        f"[{index}] {candidate['title']} "
                        f"({candidate.get('year') or 'unknown year'}) - "
                        f"TMDB ID: {candidate.get('tmdb_id', 'Unknown ID')}\n")
                file.write("\n")

def identify_movie(local_movie, candidates):
    local_movie.pop("selected_tmdb_id", None)
    local_movie.pop("candidates", None)
    local_movie.pop("status", None)

    matching_candidates = filter_candidates(local_movie, candidates)

    valid_candidates = []
    uncertain_candidates = []

    if local_movie["year"] is None:
        valid_candidates.extend(matching_candidates)
    else:
        for candidate in matching_candidates:
            if candidate.get("year") == local_movie["year"]:
                valid_candidates.append(candidate)
            elif candidate.get("year") is None:
                uncertain_candidates.append(candidate)

    if len(valid_candidates) == 0:
        if uncertain_candidates:
            status = "review"
        else:
            status = "unmatched"

    elif len(valid_candidates) == 1:
        if local_movie["year"] is None:
            status = "review"
        else:
            status = "matched"

    else:
        status = "review"

    if status == "matched":
        local_movie["selected_tmdb_id"] = valid_candidates[0]["tmdb_id"]
        local_movie["candidates"] = valid_candidates

    if status == "review":
        local_movie["candidates"] = (
            valid_candidates + uncertain_candidates
        )

    local_movie["status"] = status

def select_candidate(candidates, choice):
    try:
        choice=int(choice)
    except ValueError:
        raise ValueError("Please enter a valid number")
    if not  1<= choice <= len(candidates):
        raise ValueError(f"Choose between 1 and {len(candidates)}")
    candidate = candidates[choice-1]
    return candidate

def save_selection(local_movie, selected_candidate):
    tmdb_id = selected_candidate.get("tmdb_id")

    if (
        not isinstance(tmdb_id, int)
        or isinstance(tmdb_id, bool)
        or tmdb_id <= 0
    ):
        raise ValueError("Selected candidate must have a valid TMDB ID.")

    local_movie["selected_tmdb_id"] = tmdb_id
    local_movie["status"] = "matched"

def display_candidates(candidates):
    for index, candidate in enumerate(candidates, start=1):
        title = candidate.get("title")

        if not isinstance(title, str) or not title.strip():
            title = "Unknown title"
        year = candidate.get("year")
        tmdb_id = candidate.get("tmdb_id")

        if not (
            isinstance(year, int)
            and not isinstance(year, bool)
            and 1888 <= year <= 2100
        ):
            year = "Unknown year"

        if (
            not isinstance(tmdb_id, int)
            or isinstance(tmdb_id, bool)
            or tmdb_id <= 0
        ):
            tmdb_id = "Unknown ID"

        print(
            f"{index}. {title} "
            f"({year}) "
            f"[TMDB ID: {tmdb_id}]"
        )


def filter_candidates(local_movie, candidates):
    local_title = normalize_title(local_movie["title"])

    filtered = []

    for candidate in candidates:
        candidate_title = candidate.get("title")
        year = candidate.get("year")

        # Reject missing or invalid titles
        if not isinstance(candidate_title, str) or not candidate_title.strip():
            continue

        # Reject invalid years
        if year is not None and not (
            isinstance(year, int)
            and not isinstance(year, bool)
            and 1888 <= year <= 2100
        ):
            continue

        if local_title == normalize_title(candidate_title):
            filtered.append(candidate)

    filtered.sort(
        key=lambda candidate: candidate.get("year") or 0
    )

    return filtered

def process_movies(movies, db_path=None):
    counts = {
    "matched": 0,
    "review": 0,
    "unmatched": 0,
    "error": 0
    }
    
    for movie in movies:
        movie.pop("error", None)
        movie.pop("selected_tmdb_id", None)
        movie.pop("candidates", None)
        movie.pop("status", None)
        try:
            candidates = search_movie_with_retry(
                movie["title"],
                movie["year"]
            )
            identify_movie(movie, candidates)

        except urllib.error.URLError as error:
            movie["status"] = "error"
            movie["error"] = str(error)
        if movie["status"] != "error":
            movie["error"] = None

        counts[movie["status"]] += 1
        if db_path:
            save_movie(movie, db_path)

    return counts


def normalize_title(title):
    title = title.casefold()
    title = re.sub(r"[^a-z0-9]", "", title)
    return title


def remove_duplicates(movies):
    seen_paths = set()
    seen_movies = set()
    unique_movies = []

    for movie in movies:
        file_path = movie["file_path"]

        if file_path in seen_paths:
            continue

        seen_paths.add(file_path)

        if movie["year"] is None:
            unique_movies.append(movie)
            continue

        key = (normalize_title(movie["title"]), movie["year"])

        if key not in seen_movies:
            seen_movies.add(key)
            unique_movies.append(movie)

    return unique_movies

def save_movies(movies, output_file):
    temp_file = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=os.path.dirname(os.path.abspath(output_file)),
            delete=False
        ) as file:
            temp_file = file.name
            json.dump(movies, file, indent=4, ensure_ascii=False)

        os.replace(temp_file, output_file)

    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)

def scan_movies(directory):
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    movie_files = []

    for file_path in directory.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
            movie_files.append(file_path)

    return movie_files

def parse_movie_filename(file_path):
    filename = file_path.stem

    year_matches = list(
        re.finditer(
            r"(?<!\d)(18[89]\d|19\d{2}|20\d{2}|2100)(?!\d)",
            filename
        )
    )

    # Ignore years that appear at the beginning of the filename
    year_match = next(
        (match for match in reversed(year_matches) if match.start() > 0),
        None
    )

    if year_match:
        year = int(year_match.group(1))
        title = filename[:year_match.start()]
    else:
        year = None
        title = filename

    title = title.replace(".", " ")
    title = title.replace("_", " ")

    # Remove common punctuation around the title
    title = title.strip(" -_.()[]")

    return {
        "title": title,
        "year": year,
        "filename": file_path.name,
        "file_path": str(file_path.resolve())
    }

def main():
    movie_directory = input("Enter your movie directory: ")

    # Validate and scan movie directory first
    movie_files = scan_movies(movie_directory)

    # Load previously saved movies
    initialize_database("movies.db")
    old_movies = load_database_movies("movies.db")

    new_movies = [
        parse_movie_filename(path)
        for path in movie_files
    ]

    new_movies = remove_duplicates(new_movies)
    old_paths = get_movie_paths("movies.db")
    new_unprocessed, failed_movies = find_movies_to_process(
        old_movies,
        new_movies,
        old_paths
    )

    # Add new movies to our existing collection
    old_movies.extend(new_unprocessed)

    pending_movies = [
        movie for movie in old_movies
        if "status" not in movie
    ]

    # Process failed and pending movies
    process_movies(failed_movies, db_path="movies.db")
    process_movies(pending_movies, db_path="movies.db")

    # Generate report and review unresolved movies
    generate_review_report(old_movies, "review_report.txt")
    review_movies(old_movies, db_path="movies.db")

    # Update report and export
    generate_review_report(old_movies, "review_report.txt")
    export_letterboxd_csv(old_movies, "letterboxd_import.csv")

    print(f"\nScanned: {len(movie_files)} files")
    print(f"New movies: {len(new_unprocessed)}")
    print(f"Previously failed movies retried: {len(failed_movies)}")
    print(f"Total movies in database: {len(old_movies)}")

if __name__ == "__main__":
    main()



