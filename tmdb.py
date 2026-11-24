import os
import json
import urllib.request
import urllib.parse


import time
import urllib.error

def search_movie_with_retry(title, year=None, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return search_movie(title, year)

        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 503):
                raise

            if attempt == max_attempts - 1:
                raise

        except urllib.error.URLError:
            if attempt == max_attempts - 1:
                raise

        delay = 2 ** (attempt + 1)
        time.sleep(delay)

def extract_movie_info(movie):
    release_date = movie.get("release_date", "")

    return {
        "tmdb_id": movie["id"],
        "title": movie["title"],
        "year": int(release_date[:4]) if release_date else None,
        "release_date": release_date,
    }

def search_movie(title, year=None):
    token = os.getenv("TMDB_READ_ACCESS_TOKEN")

    if not token:
        raise RuntimeError("TMDB API token is missing")

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "query": title,
    }

    if year:
        params["year"] = year

    query_string = urllib.parse.urlencode(params)

    request = urllib.request.Request(
        f"{url}?{query_string}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
    )

    with urllib.request.urlopen(request) as response:
        data = json.loads(response.read().decode("utf-8"))

    movies = [extract_movie_info(result) for result in data["results"]]
    return movies
    
if __name__ == "__main__":
    movies = search_movie("The Thing", 1982)

    for movie in movies:
        print(movie)
