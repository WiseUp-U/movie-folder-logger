import os
import csv
from main import scan_movies
import sys
import subprocess
from migrate import migrate_database
from database import (
    initialize_database,
    save_movie,
    load_movies as load_database_movies,
    get_movie_paths,
)
import sqlite3
import unittest
import urllib.error
from main import normalize_title, save_movies, load_movies, select_candidate, save_selection, generate_review_report
from main import parse_movie_filename, remove_duplicates, identify_movie, review_movies,display_candidates, export_letterboxd_csv
from pathlib import Path
import tempfile
from unittest.mock import patch
from main import process_movies, main
from main import find_movies_to_process


class TestMain(unittest.TestCase):

    def test_successfully_processed_movie_is_not_searched_again(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            movie_dir = Path(temp_dir) / "movies"
            movie_dir.mkdir()

            movie_file = movie_dir / "Interstellar (2014).mkv"
            movie_file.touch()

            original_directory = os.getcwd()

            try:
                os.chdir(temp_dir)

                with patch("builtins.input", return_value=str(movie_dir)):
                    with patch(
                        "main.search_movie_with_retry",
                        return_value=[
                            {
                                "title": "Interstellar",
                                "year": 2014,
                                "tmdb_id": 157336
                            }
                        ]
                    ) as mock_search:

                        # First run: discover and process the movie.
                        main()

                        # Second run: recognize it as already processed.
                        main()

                self.assertEqual(mock_search.call_count, 1)

                saved_movies = load_database_movies("movies.db")

                self.assertEqual(len(saved_movies), 1)
                self.assertEqual(saved_movies[0]["status"], "matched")
                self.assertEqual(
                    saved_movies[0]["selected_tmdb_id"],
                    157336
                )

            finally:
                os.chdir(original_directory)

    def test_failed_movie_is_retried_on_next_application_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            movie_dir = Path(temp_dir) / "movies"
            movie_dir.mkdir()

            movie_file = movie_dir / "Interstellar (2014).mkv"
            movie_file.touch()

            original_directory = os.getcwd()

            try:
                os.chdir(temp_dir)

                with patch(
                    "builtins.input",
                    return_value=str(movie_dir)
                ):
                    with patch(
                        "main.search_movie_with_retry",
                        side_effect=[
                            urllib.error.URLError("Network unavailable"),
                            [
                                {
                                    "title": "Interstellar",
                                    "year": 2014,
                                    "tmdb_id": 157336
                                }
                            ]
                        ]
                    ) as mock_search:

                        # First application run.
                        main()

                        first_run_movies = load_database_movies("movies.db")

                        self.assertEqual(
                            first_run_movies[0]["status"],
                            "error"
                        )

                        # Second application run.
                        main()

                        second_run_movies = load_database_movies("movies.db")

                self.assertEqual(
                    second_run_movies[0]["status"],
                    "matched"
                )

                self.assertEqual(
                    second_run_movies[0]["selected_tmdb_id"],
                    157336
                )

                self.assertEqual(mock_search.call_count, 2)

            finally:
                os.chdir(original_directory)

    @patch("main.export_letterboxd_csv")
    @patch("main.review_movies")
    @patch("main.generate_review_report")
    @patch("main.process_movies")
    @patch("main.get_movie_paths", return_value=set())
    @patch("main.load_database_movies")
    @patch("main.scan_movies", return_value=[])
    @patch("main.initialize_database")
    @patch("builtins.input")
    def test_failed_movies_are_retried(
        self,
        mock_input,
        mock_initialize,
        mock_scan,
        mock_load,
        mock_paths,
        mock_process,
        mock_report,
        mock_review,
        mock_export
    ):
        failed_movie = {
            "title": "Arrival",
            "year": 2016,
            "file_path": "/movies/Arrival (2016).mkv",
            "status": "error"
        }

        mock_input.return_value = "/movies"
        mock_load.return_value = [failed_movie]

        main()

        mock_process.assert_any_call(
            [failed_movie],
            db_path="movies.db"
        )

    @patch("main.export_letterboxd_csv")
    @patch("main.review_movies")
    @patch("main.generate_review_report")
    @patch("main.process_movies")
    @patch("main.get_movie_paths")
    @patch("main.load_database_movies", return_value=[])
    @patch("main.parse_movie_filename")
    @patch("main.scan_movies")
    @patch("main.initialize_database")
    @patch("builtins.input")
    def test_existing_movie_is_not_processed_again(
        self,
        mock_input,
        mock_initialize,
        mock_scan,
        mock_parse,
        mock_load,
        mock_paths,
        mock_process,
        mock_report,
        mock_review,
        mock_export
    ):
        movie_path = Path("/movies/Arrival (2016).mkv")

        movie = {
            "title": "Arrival",
            "year": 2016,
            "file_path": str(movie_path),
            "filename": movie_path.name
        }

        mock_input.return_value = "/movies"
        mock_scan.return_value = [movie_path]
        mock_parse.return_value = movie
        mock_paths.return_value = {str(movie_path)}

        main()

        self.assertEqual(mock_process.call_count, 2)

        self.assertTrue(
            all(
                not call.args[0]
                for call in mock_process.call_args_list
            )
        )

    @patch("main.export_letterboxd_csv")
    @patch("main.review_movies")
    @patch("main.generate_review_report")
    @patch("main.process_movies")
    @patch("main.get_movie_paths", return_value=set())
    @patch("main.load_database_movies", return_value=[])
    @patch("main.parse_movie_filename")
    @patch("main.scan_movies")
    @patch("main.initialize_database")
    @patch("builtins.input")
    def test_new_movies_are_sent_for_processing(
        self,
        mock_input,
        mock_initialize,
        mock_scan,
        mock_parse,
        mock_load,
        mock_paths,
        mock_process,
        mock_report,
        mock_review,
        mock_export
    ):
        movie_path = Path("/movies/Arrival (2016).mkv")

        movie = {
            "title": "Arrival",
            "year": 2016,
            "file_path": str(movie_path),
            "filename": movie_path.name
        }

        mock_input.return_value = "/movies"
        mock_scan.return_value = [movie_path]
        mock_parse.return_value = movie

        main()

        mock_process.assert_any_call(
            [movie],
            db_path="movies.db"
        )

    @patch("main.export_letterboxd_csv")
    @patch("main.review_movies")
    @patch("main.generate_review_report")
    @patch("main.process_movies")
    @patch("main.get_movie_paths", return_value=set())
    @patch("main.load_database_movies", return_value=[])
    @patch("main.initialize_database")
    @patch("builtins.input")
    def test_workflow_execution_order(
        self,
        mock_input,
        mock_initialize,
        mock_load,
        mock_paths,
        mock_process,
        mock_report,
        mock_review,
        mock_export
    ):
        call_order = []

        mock_process.side_effect = lambda *args, **kwargs: call_order.append("process")
        mock_report.side_effect = lambda *args, **kwargs: call_order.append("report")
        mock_review.side_effect = lambda *args, **kwargs: call_order.append("review")
        mock_export.side_effect = lambda *args, **kwargs: call_order.append("export")

        with tempfile.TemporaryDirectory() as temp_dir:
            mock_input.return_value = temp_dir

            main()

        self.assertEqual(
            call_order,
            ["process", "process", "report", "review", "report", "export"]
        )

    @patch("main.export_letterboxd_csv")
    @patch("main.review_movies")
    @patch("main.generate_review_report")
    @patch("main.process_movies")
    @patch("main.get_movie_paths", return_value=set())
    @patch("main.load_database_movies", return_value=[])
    @patch("main.initialize_database")
    @patch("builtins.input")
    def test_valid_directory_initializes_database(
        self,
        mock_input,
        mock_initialize,
        mock_load,
        mock_paths,
        mock_process,
        mock_report,
        mock_review,
        mock_export
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_input.return_value = temp_dir

            main()

        mock_initialize.assert_called_once_with("movies.db")

    @patch("builtins.input")
    @patch("main.initialize_database")
    def test_file_path_does_not_initialize_database(
        self, mock_initialize, mock_input
    ):
        with tempfile.NamedTemporaryFile() as temp_file:
            mock_input.return_value = temp_file.name

            with self.assertRaises(NotADirectoryError):
                main()

        mock_initialize.assert_not_called()

    @patch("builtins.input", return_value="/nonexistent/directory")
    @patch("main.initialize_database")
    def test_invalid_directory_does_not_initialize_database(
        self, mock_initialize, mock_input
    ):
        with self.assertRaises(FileNotFoundError):
            main()

        mock_initialize.assert_not_called()


class TestExportLetterboxdCSV(unittest.TestCase):

    def test_export_warns_when_selected_id_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movies = [
                {
                    "title": "Arrival",
                    "selected_tmdb_id": 999999,
                    "candidates": [
                        {
                            "tmdb_id": 329865,
                            "title": "Arrival",
                            "year": 2016
                        }
                    ]
                }
            ]

            export_letterboxd_csv(movies, output_file)

            with open(output_file, encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

            self.assertEqual(rows, [["tmdbID", "Title", "Year"]])

    def test_export_skips_candidate_with_whitespace_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movies = [
                {
                    "title": "Arrival",
                    "selected_tmdb_id": 329865,
                    "candidates": [
                        {
                            "tmdb_id": 329865,
                            "title": "   ",
                            "year": 2016
                        }
                    ]
                }
            ]

            export_letterboxd_csv(movies, output_file)

            with open(output_file, encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

            self.assertEqual(rows, [["tmdbID", "Title", "Year"]])

    def test_export_handles_candidate_without_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movies = [
                {
                    "title": "Arrival",
                    "selected_tmdb_id": 329865,
                    "candidates": [
                        {
                            "tmdb_id": 329865,
                            "year": 2016
                        }
                    ]
                }
            ]

            export_letterboxd_csv(movies, output_file)

            with open(output_file, encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

            self.assertEqual(rows, [["tmdbID", "Title", "Year"]])

    def test_export_handles_candidate_without_year(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movies = [
                {
                    "title": "Arrival",
                    "selected_tmdb_id": 329865,
                    "candidates": [
                        {
                            "tmdb_id": 329865,
                            "title": "Arrival",
                            "year": None
                        }
                    ]
                }
            ]

            export_letterboxd_csv(movies, output_file)

            with open(output_file, encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

            self.assertEqual(
                rows,
                [
                    ["tmdbID", "Title", "Year"],
                    ["329865", "Arrival", ""]
                ]
            )
    def test_export_includes_automatically_matched_movie(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movie = {
                "title": "Interstellar",
                "year": 2014
            }

            candidates = [
                {
                    "tmdb_id": 157336,
                    "title": "Interstellar",
                    "year": 2014
                }
            ]

            identify_movie(movie, candidates)

            export_letterboxd_csv([movie], output_file)

            with open(output_file, encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

            self.assertEqual(
                rows,
                [
                    ["tmdbID", "Title", "Year"],
                    ["157336", "Interstellar", "2014"]
                ]
            )

    def test_export_excludes_unselected_movies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movies = [
                {
                    "title": "Arrival",
                    "status": "review",
                    "candidates": [
                        {
                            "tmdb_id": 329865,
                            "title": "Arrival",
                            "year": 2016
                        }
                    ]
                }
            ]

            export_letterboxd_csv(movies, output_file)

            with open(output_file, encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

            self.assertEqual(rows, [["tmdbID", "Title", "Year"]])

    def test_export_handles_movie_without_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movies = [
                {
                    "title": "Arrival",
                    "selected_tmdb_id": 329865
                }
            ]

            export_letterboxd_csv(movies, output_file)

            with open(output_file, encoding="utf-8") as file:
                content = file.read()

            self.assertIn("tmdbID,Title,Year", content)

    def test_export_continues_after_missing_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "letterboxd.csv"

            movies = [
                {
                    "title": "Arrival",
                    "selected_tmdb_id": 999999,
                    "candidates": []
                },
                {
                    "title": "Interstellar",
                    "selected_tmdb_id": 157336,
                    "candidates": [
                        {
                            "tmdb_id": 157336,
                            "title": "Interstellar",
                            "year": 2014
                        }
                    ]
                }
            ]

            export_letterboxd_csv(movies, output_file)

            with open(output_file, encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

            self.assertEqual(
                rows,
                [
                    ["tmdbID", "Title", "Year"],
                    ["157336", "Interstellar", "2014"]
                ]
            )


class TestGenerateReviewReport(unittest.TestCase):


    def test_report_excludes_non_review_movies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "report.txt"

            movies = [
                {
                    "title": "Interstellar",
                    "year": 2014,
                    "status": "matched",
                    "candidates": []
                },
                {
                    "title": "Arrival",
                    "year": 2016,
                    "status": "unmatched",
                    "candidates": []
                }
            ]

            generate_review_report(movies, output_file)

            with open(output_file, encoding="utf-8") as file:
                report = file.read()

            self.assertEqual(report, "")

    def test_report_handles_empty_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "report.txt"

            movies = [
                {
                    "title": "Arrival",
                    "year": 2016,
                    "status": "review",
                    "candidates": []
                }
            ]

            generate_review_report(movies, output_file)

            with open(output_file, encoding="utf-8") as file:
                report = file.read()

            self.assertIn("Arrival (2016)", report)
            self.assertNotIn("[1]", report)

    def test_report_handles_movie_without_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "report.txt"

            movies = [
                {
                    "title": "Arrival",
                    "year": 2016,
                    "status": "review"
                }
            ]

            generate_review_report(movies, output_file)

            with open(output_file, encoding="utf-8") as file:
                report = file.read()

            self.assertIn("Arrival (2016)", report)


    def test_report_handles_candidate_without_tmdb_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "report.txt"

            movies = [
                {
                    "title": "Arrival",
                    "year": 2016,
                    "status": "review",
                    "candidates": [
                        {
                            "title": "Arrival",
                            "year": 2016
                        }
                    ]
                }
            ]

            generate_review_report(movies, output_file)

            with open(output_file, encoding="utf-8") as file:
                report = file.read()

            self.assertIn("TMDB ID: Unknown ID", report)

    def test_report_handles_candidate_without_year(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "report.txt"

            movies = [
                {
                    "title": "Arrival",
                    "year": 2016,
                    "status": "review",
                    "candidates": [
                        {
                            "tmdb_id": 329865,
                            "title": "Arrival"
                        }
                    ]
                }
            ]

            generate_review_report(movies, output_file)

            with open(output_file, encoding="utf-8") as file:
                report = file.read()

            self.assertIn(
                "[1] Arrival (unknown year) - TMDB ID: 329865",
                report
            )


class TestDisplayCandidates(unittest.TestCase):


    @patch("builtins.print")
    def test_displays_unknown_id_for_invalid_tmdb_id(self, mock_print):
        candidates = [
            {
                "title": "Arrival",
                "year": 2016,
                "tmdb_id": "abc"
            }
        ]

        display_candidates(candidates)

        mock_print.assert_called_once_with(
            "1. Arrival (2016) [TMDB ID: Unknown ID]"
        )

    @patch("builtins.print")
    def test_displays_unknown_year_for_invalid_year(self, mock_print):
        candidates = [
            {
                "title": "Arrival",
                "year": "unknown",
                "tmdb_id": 329865
            }
        ]

        display_candidates(candidates)

        mock_print.assert_called_once_with(
            "1. Arrival (Unknown year) [TMDB ID: 329865]"
        )

    @patch("builtins.print")
    def test_displays_unknown_title_for_blank_title(self, mock_print):
        candidates = [
            {
                "title": "   ",
                "year": 2016,
                "tmdb_id": 329865
            }
        ]

        display_candidates(candidates)

        mock_print.assert_called_once_with(
            "1. Unknown title (2016) [TMDB ID: 329865]"
        )

    @patch("builtins.print")
    def test_displays_candidate_with_missing_fields(self, mock_print):
        candidates = [
            {
                "title": "Arrival"
            }
        ]

        display_candidates(candidates)

        mock_print.assert_called_once_with(
            "1. Arrival (Unknown year) [TMDB ID: Unknown ID]"
        )


class TestReviewMovies(unittest.TestCase):

    def test_failed_save_preserves_original_database_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"
            initialize_database(db_path)

            movie = {
                "file_path": "/movies/Interstellar.mkv",
                "title": "Interstellar",
                "year": 2014,
                "status": "review",
                "candidates": [
                    {"title": "Interstellar", "year": 2014, "tmdb_id": 1}
                ]
            }

            save_movie(movie, db_path)

            original_database_movie = load_database_movies(db_path)[0]

            with patch("builtins.input", return_value="1"):
                with patch(
                    "main.save_movie",
                    side_effect=RuntimeError("Simulated database failure")
                ):
                    with self.assertRaises(RuntimeError):
                        review_movies([movie], db_path)

            # Check the in-memory movie.
            self.assertEqual(movie["status"], "review")
            self.assertNotIn("selected_tmdb_id", movie)

            # Check the actual database.
            saved_movie = load_database_movies(db_path)[0]

            self.assertEqual(
                saved_movie["status"],
                original_database_movie["status"]
            )
            self.assertNotIn("selected_tmdb_id", saved_movie)

    def test_previous_selections_survive_crash_during_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"
            initialize_database(db_path)

            movies = [
                {
                    "file_path": "/movies/Interstellar.mkv",
                    "title": "Interstellar",
                    "year": 2014,
                    "status": "review",
                    "candidates": [
                        {"title": "Interstellar", "year": 2014, "tmdb_id": 1}
                    ]
                },
                {
                    "file_path": "/movies/Inception.mkv",
                    "title": "Inception",
                    "year": 2010,
                    "status": "review",
                    "candidates": [
                        {"title": "Inception", "year": 2010, "tmdb_id": 2}
                    ]
                },
                {
                    "file_path": "/movies/Arrival.mkv",
                    "title": "Arrival",
                    "year": 2016,
                    "status": "review",
                    "candidates": [
                        {"title": "Arrival", "year": 2016, "tmdb_id": 3}
                    ]
                }
            ]

            # Save all three movies before manual review.
            for movie in movies:
                save_movie(movie, db_path)

            save_count = 0

            def save_then_crash(movie, path):
                nonlocal save_count
                save_count += 1

                if save_count == 3:
                    raise RuntimeError("Simulated crash")

                return save_movie(movie, path)

            with patch("builtins.input", side_effect=["1", "1", "1"]):
                with patch("main.save_movie", side_effect=save_then_crash):
                    with self.assertRaises(RuntimeError):
                        review_movies(movies, db_path)

            saved_movies = load_database_movies(db_path)

            statuses = {
                movie["title"]: movie["status"]
                for movie in saved_movies
            }

            self.assertEqual(statuses["Interstellar"], "matched")
            self.assertEqual(statuses["Inception"], "matched")
            self.assertEqual(statuses["Arrival"], "review")

    def test_skips_movie_with_empty_candidates(self):
        movie = {
            "title": "Arrival",
            "year": 2016,
            "status": "review",
            "candidates": []
        }

        with patch("main.display_candidates") as mock_display:
            with patch("builtins.input") as mock_input:
                review_movies([movie])

        mock_display.assert_not_called()
        mock_input.assert_not_called()
        self.assertEqual(movie["status"], "review")


    @patch("builtins.input", return_value="1")
    @patch("main.save_movie", side_effect=sqlite3.OperationalError("Database error"))
    def test_does_not_leave_movie_matched_when_database_save_fails(
        self,
        mock_save,
        mock_input
    ):
        movie = {
            "title": "Arrival",
            "year": 2016,
            "status": "review",
            "candidates": [
                {
                    "tmdb_id": 329865,
                    "title": "Arrival",
                    "year": 2016
                }
            ]
        }

        with self.assertRaises(sqlite3.OperationalError):
            review_movies([movie], db_path="movies.db")

        self.assertEqual(movie["status"], "review")
        self.assertNotIn("selected_tmdb_id", movie)
        mock_save.assert_called_once()

    @patch("main.save_movie")
    @patch("builtins.input", side_effect=["abc", "5", "1"])
    def test_retries_until_valid_selection(
        self,
        mock_input,
        mock_save
    ):
        movie = {
            "title": "Arrival",
            "year": 2016,
            "status": "review",
            "candidates": [
                {
                    "tmdb_id": 329865,
                    "title": "Arrival",
                    "year": 2016
                }
            ]
        }

        with patch("main.display_candidates"):
            review_movies([movie], db_path="movies.db")

        self.assertEqual(movie["status"], "matched")
        self.assertEqual(movie["selected_tmdb_id"], 329865)
        self.assertEqual(mock_input.call_count, 3)
        mock_save.assert_called_once()


    @patch("builtins.input", side_effect=["1", "1", "1"])
    def test_previous_selections_remain_saved_when_later_save_fails(
        self,
        mock_input
    ):
        movies = [
            {
                "title": f"Movie {i}",
                "year": 2020,
                "status": "review",
                "candidates": [
                    {
                        "tmdb_id": 100 + i,
                        "title": f"Movie {i}",
                        "year": 2020
                    }
                ]
            }
            for i in range(1, 4)
        ]

        with patch("main.display_candidates"):
            with patch(
                "main.save_movie",
                side_effect=[None, None, sqlite3.OperationalError("Database error")]
            ) as mock_save:
                with self.assertRaises(sqlite3.OperationalError):
                    review_movies(movies, db_path="movies.db")

        self.assertEqual(movies[0]["status"], "matched")
        self.assertEqual(movies[1]["status"], "matched")
        self.assertEqual(movies[2]["status"], "review")

        self.assertEqual(mock_save.call_count, 3)


class TestDatabase(unittest.TestCase):

    def test_saving_same_movie_updates_existing_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)

            movie = {
                "file_path": "/movies/interstellar.mkv",
                "title": "Interstellar",
                "year": 2014,
                "status": "matched",
                "selected_tmdb_id": 157336,
                "filename": "Intersteller (2014).mkv"
            }

            save_movie(movie, db_path)
            movie.pop("filename")
            movie.pop("year")
            save_movie(movie, db_path)
            movie["error"] = "Connection timed out"
            save_movie(movie, db_path)

            # Change the existing record
            movie["status"] = "review"
            movie.pop("selected_tmdb_id")

            save_movie(movie, db_path)

            saved_movies = load_database_movies(db_path)

            movie["candidates"] = [
                {"tmdb_id": 157336, "title": "Interstellar", "year": 2014}
            ]
            save_movie(movie, db_path)

            movie.pop("candidates")
            save_movie(movie, db_path)
            movie["status"] = "matched"
            save_movie(movie, db_path)
            movie.pop("status")
            save_movie(movie, db_path)
            movie["selected_tmdb_id"] = None
            save_movie(movie, db_path)
            saved_movies = load_database_movies(db_path)
            self.assertEqual(saved_movies[0]["status"], "matched")
            self.assertEqual(
                saved_movies[0]["candidates"],
                [{"tmdb_id": 157336, "title": "Interstellar", "year": 2014}]
            )

            self.assertEqual(len(saved_movies), 1)
            
            self.assertNotIn("selected_tmdb_id", saved_movies[0])
            self.assertEqual(
                saved_movies[0]["error"],
                "Connection timed out"
            )
            self.assertEqual(saved_movies[0]["year"], 2014)
            self.assertEqual(saved_movies[0]["filename"], "Intersteller (2014).mkv")

    def test_saving_movie_with_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)
            movie = {
                "file_path": "/movies/interstellar.mkv",
                "title": "Interstellar",
                "year": 2014,
                "candidates": [
                    {
                        "tmdb_id": 157336,
                        "title": "Interstellar",
                        "year": 2014
                    },
                    {
                        "tmdb_id": 49051,
                        "title": "The Hobbit",
                        "year": 2012
                    }
                ]
            }
            save_movie(movie, db_path)

            saved_movies = load_database_movies(db_path)
            self.assertEqual(
                saved_movies[0]["candidates"],
                movie["candidates"]
            )

    def test_get_movie_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)

            movies = [
                {
                    "title": "Interstellar",
                    "year": 2014,
                    "file_path": "/movies/interstellar.mkv"
                },
                {
                    "title": "Inception",
                    "year": 2010,
                    "file_path": "/movies/inception.mkv"
                },
            ]
            for movie in movies:
                save_movie(movie, db_path)
            paths = get_movie_paths(db_path)
            expected_paths = {
                movie["file_path"]
                for movie in movies
            }
            self.assertEqual(paths, expected_paths)

    def test_rejects_movie_without_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)

            movie = {
                "file_path": "/movies/interstellar.mkv",
                "year": 2014
            }

            with self.assertRaises((sqlite3.IntegrityError, ValueError)):
                save_movie(movie, db_path)

    def test_rejects_movie_without_file_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)

            movie = {
                "title": "Intersterllar",
                "year": 2014,
            }

            with self.assertRaises(sqlite3.IntegrityError):
                save_movie(movie, db_path)

    def test_rejects_invalid_year(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)

            movie = {
                "title": "Interstellar",
                "year": "two thousand",
                "file_path": "/movies/interstellar.mkv",
            }

            with self.assertRaises(sqlite3.IntegrityError):
                save_movie(movie, db_path)

    def test_rejects_float_year(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)

            movie = {
                "title": "Interstellar",
                "year": 2014.5,
                "file_path": "/movies/interstellar.mkv",
            }

            with self.assertRaises(sqlite3.IntegrityError):
                save_movie(movie, db_path)


    def test_rejects_year_outside_valid_range(self):
    	with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"
            initialize_database(db_path)

            for year in (1887, 2101):
            	movie = {
                    "title": "Interstellar",
                    "year": year,
                    "file_path": f"/movies/interstellar_{year}.mkv",
            	}

            	with self.subTest(year=year):
                    with self.assertRaises(sqlite3.IntegrityError):
                        save_movie(movie, db_path)

    def test_migration_rejects_missing_movies_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "empty.db"

            with self.assertRaisesRegex(
                ValueError,
                "Movies table does not exist."
            ):
                migrate_database(db_path)

    def test_migration_preserves_existing_movie_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "old_movies.db"

            with sqlite3.connect(db_path) as connection:
                connection.execute("""
                    CREATE TABLE movies (
                        file_path TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        year INTEGER,
                        filename TEXT,
                        selected_tmdb_id INTEGER,
                        status TEXT,
                        error TEXT,
                        candidates TEXT
                    )
                """)
                connection.execute("""
                    INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "/movies/interstellar.mkv",
                    "Interstellar",
                    2014,
                    "Interstellar (2014).mkv",
                    157336,
                    "matched",
                    None,
                    '[{"tmdb_id": 157336, "title": "Interstellar", "year": 2014}]'
                ))
            migrate_database(db_path)

            with sqlite3.connect(db_path) as connection:
                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]

            self.assertEqual(version, 1)

            with sqlite3.connect(db_path) as connection:
                movie = connection.execute("""
                    SELECT *
                    FROM movies
                    WHERE file_path = ?
                """, ("/movies/interstellar.mkv",)).fetchone()
            self.assertEqual(movie, (
                "/movies/interstellar.mkv",
                "Interstellar",
                2014,
                "Interstellar (2014).mkv",
                157336,
                "matched",
                None,
                '[{"tmdb_id": 157336, "title": "Interstellar", "year": 2014}]'
            ))
    def test_migration_rolls_back_on_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "old_movies.db"
            with sqlite3.connect(db_path) as connection:
                connection.execute("""
                    CREATE TABLE movies (
                        file_path TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        year INTEGER,
                        filename TEXT,
                        selected_tmdb_id INTEGER,
                        status TEXT,
                        error TEXT,
                        candidates TEXT
                    )
                """)

                connection.execute("""
                    INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "/movies/example.mkv",
                    "Example",
                    "two thousand",
                    "Example.mkv",
                    None,
                    "matched",
                    None,
                    None
                ))
            with self.assertRaises(sqlite3.IntegrityError):
                migrate_database(db_path)

            with sqlite3.connect(db_path) as connection:
                movie = connection.execute("""
                    SELECT *
                    FROM movies
                """).fetchone()
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0],
                    0
                )
            self.assertEqual(movie, (
                "/movies/example.mkv",
                "Example",
                "two thousand",
                "Example.mkv",
                None,
                "matched",
                None,
                None
            ))
            

    def test_accepts_year_1888(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"
            initialize_database(db_path)

            movie = {
                "file_path": "/movies/example.mkv",
                "title": "Example",
                "year": 1888
            }

            save_movie(movie, db_path)

    def test_accepts_year_2100(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"
            initialize_database(db_path)

            movie = {
                "file_path": "/movies/example.mkv",
                "title": "Example",
                "year": 2100
            }

            save_movie(movie, db_path)

    def test_rejects_unsupported_database_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"
            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA user_version = 2")

            with self.assertRaisesRegex(
                ValueError, "Unsupported database version: 2"
            ):
                migrate_database(db_path)

    def test_initialize_preserves_existing_database_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"
            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA user_version = 2")

            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]

            self.assertEqual(version, 2)

    def test_migration_rolls_back_when_file_path_is_null(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "old_movies.db"
            with sqlite3.connect(db_path) as connection:
                connection.execute("""
                    CREATE TABLE movies (
                        file_path TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        year INTEGER,
                        filename TEXT,
                        selected_tmdb_id INTEGER,
                        status TEXT,
                        error TEXT,
                        candidates TEXT
                    )
                """)
                connection.execute("""
                    INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    None,
                    "Interstellar",
                    2014,
                    "Interstellar (2014).mkv",
                    157336,
                    "matched",
                    None,
                    None
                ))
            with self.assertRaises(sqlite3.IntegrityError):
                migrate_database(db_path)
            with sqlite3.connect(db_path) as connection:
                movie = connection.execute("""
                    SELECT file_path, title, year
                    FROM movies
                """).fetchone()

                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]

            self.assertEqual(movie, (None, "Interstellar", 2014))
            self.assertEqual(version, 0)

    def test_migration_recovers_after_process_crash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "old_movies.db"
            with sqlite3.connect(db_path) as connection:
                connection.execute("""
                    CREATE TABLE movies (
                        file_path TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        year INTEGER,
                        filename TEXT,
                        selected_tmdb_id INTEGER,
                        status TEXT,
                        error TEXT,
                        candidates TEXT
                    )
                """)

                connection.execute("""
                    INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "/movies/interstellar.mkv",
                    "Interstellar",
                    2014,
                    "Interstellar (2014).mkv",
                    157336,
                    "matched",
                    None,
                    None
                ))
            script = """
            import os
            import sqlite3

            db_path = r'{}'

            with sqlite3.connect(db_path) as connection:
                connection.execute("BEGIN")

                connection.execute('''
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
                ''')

                connection.execute('''
                    INSERT INTO movies_new
                    SELECT * FROM movies
                ''')

                os._exit(1)
            """.format(db_path)
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True
            )
            self.assertEqual(result.returncode, 1)

            with sqlite3.connect(db_path) as connection:
                movie = connection.execute("""
                    SELECT file_path, title, year
                    FROM movies
                """).fetchone()
                tables = connection.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                """).fetchall()
                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
            self.assertEqual(
                movie,
                ("/movies/interstellar.mkv", "Interstellar", 2014)
            )
            self.assertEqual(tables, [("movies",)])
            self.assertEqual(version, 0)


class TestCrashRecovery(unittest.TestCase):
    @patch("main.search_movie_with_retry")
    def test_recovers_after_crash(self, mock_search):
        movies = [
            {"title": "Interstellar", "year": 2014, "file_path": "/movies/interstellar.mkv"},
            {"title": "Inception", "year": 2010, "file_path": "/movies/inception.mkv"},
            {"title": "The Matrix", "year": 1999, "file_path": "/movies/matrix.mkv"},
        ]

        mock_search.side_effect = [
            [{"tmdb_id": 157336, "title": "Interstellar", "year": 2014}],
            [{"tmdb_id": 27205, "title": "Inception", "year": 2010}],
            RuntimeError("Simulated crash"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "movies.db"

            initialize_database(db_path)

            with self.assertRaises(RuntimeError):
                process_movies(movies, db_path=str(db_path))

            saved_movies = load_database_movies(db_path)

            self.assertEqual(saved_movies[0]["status"], "matched")
            self.assertEqual(saved_movies[1]["status"], "matched")
            self.assertEqual(len(saved_movies), 2)


class TestResumeWorkflow(unittest.TestCase):
    @patch("main.search_movie_with_retry")
    def test_resume_workflow(self, mock_search):
        old_movies = [
            {
                "title": "Interstellar",
                "year": 2014,
                "file_path": "/movies/interstellar.mkv",
                "status": "matched",
                "selected_tmdb_id": 157336
            },
            {
                "title": "The Matrix",
                "year": 1999,
                "file_path": "/movies/matrix.mkv",
                "status": "error"
            },
            {
                "title": "Inception",
                "year": 2010,
                "file_path": "/movies/inception.mkv",
                "status": "matched",
                "selected_tmdb_id": 27205
            }
        ]
        new_movies = [
            {
                "title": "Interstellar",
                "year": 2014,
                "file_path": "/movies/interstellar.mkv"
            },
            {
                "title": "Arrival",
                "year": 2016,
                "file_path": "/movies/arrival.mkv"
            }
        ]

        old_paths = {
            movie["file_path"]
            for movie in old_movies
        }

        mock_search.side_effect = [
            [
                {
                    "tmdb_id": 603,
                    "title": "The Matrix",
                    "year": 1999
                }
            ],
            [
                {
                    "tmdb_id": 329865,
                    "title": "Arrival",
                    "year": 2016
                }
            ]
        ]
        new_unprocessed, failed_movies = find_movies_to_process(
            old_movies,
            new_movies,
            old_paths
            )
        process_movies(failed_movies)
        process_movies(new_unprocessed)
        old_movies.extend(new_unprocessed)

        # Exactly two TMDB searches
        self.assertEqual(mock_search.call_count, 2)

        # Previously matched movies remain unchanged
        self.assertEqual(old_movies[0]["selected_tmdb_id"], 157336)
        self.assertEqual(old_movies[2]["selected_tmdb_id"], 27205)

        # Previously failed movie is now matched
        self.assertEqual(old_movies[1]["status"], "matched")
        self.assertEqual(old_movies[1]["selected_tmdb_id"], 603)

        # New movie was added and matched
        self.assertEqual(len(old_movies), 4)
        self.assertEqual(old_movies[3]["title"], "Arrival")
        self.assertEqual(old_movies[3]["status"], "matched")
        self.assertEqual(old_movies[3]["selected_tmdb_id"], 329865)


class TestFindMoviesToProcess(unittest.TestCase):

    def test_separates_new_and_failed_movies(self):
        old_movies = [
            {
                "title": "Interstellar",
                "year": 2014,
                "file_path": "/movies/interstellar.mkv",
                "status": "matched"
            },
            {
                "title": "The Matrix",
                "year": 1999,
                "file_path": "/movies/matrix.mkv",
                "status": "error"
            }
        ]

        new_movies = [
            {
                "title": "Interstellar",
                "year": 2014,
                "file_path": "/movies/interstellar.mkv"
            },
            {
                "title": "Arrival",
                "year": 2016,
                "file_path": "/movies/arrival.mkv"
            }
        ]
        old_paths = {
            "/movies/interstellar.mkv",
            "/movies/matrix.mkv",
        }

        new_unprocessed, failed_movies = find_movies_to_process(
            old_movies,
            new_movies,
            old_paths
        )

        self.assertEqual(len(new_unprocessed), 1)
        self.assertEqual(new_unprocessed[0]["title"], "Arrival")

        self.assertEqual(len(failed_movies), 1)
        self.assertEqual(failed_movies[0]["title"], "The Matrix")

class TestProcessMovies(unittest.TestCase):

    @patch("main.search_movie_with_retry")
    def test_processes_new_movie(self, mock_search):
        movie = {
            "title": "Interstellar",
            "year": 2014
        }

        mock_search.return_value = [
            {
                "tmdb_id": 157336,
                "title": "Interstellar",
                "year": 2014
            }
        ]

        counts = process_movies([movie])

        mock_search.assert_called_once_with("Interstellar", 2014)

        self.assertEqual(movie["status"], "matched")
        self.assertEqual(movie["selected_tmdb_id"], 157336)
        self.assertEqual(counts["matched"], 1)

    @patch("main.search_movie_with_retry")
    def test_handles_network_error(self, mock_search):
        movie = {
            "title": "Interstellar",
            "year": 2014
        }

        mock_search.side_effect = urllib.error.URLError(
            "Connection failed"
        )

        counts = process_movies([movie])

        self.assertEqual(movie["status"], "error")
        self.assertIn("Connection failed", movie["error"])
        self.assertEqual(counts["error"], 1)

class TestMoviePersistence(unittest.TestCase):

    def test_failed_save_preserves_original_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "movies.json"

            original_movies = [
                {"title": "Interstellar", "year": 2014}
            ]

            save_movies(original_movies, output_file)

            with patch("main.json.dump") as mock_dump:
                mock_dump.side_effect = RuntimeError("Simulated write failure")

                with self.assertRaises(RuntimeError):
                    save_movies(
                        [{"title": "Inception", "year": 2010}],
                        output_file
                    )

            saved_movies = load_movies(output_file)

            self.assertEqual(saved_movies, original_movies)

    def test_save_and_load_movies(self):
        movies = [
            {
                "title": "Interstellar",
                "year": 2014,
                "status": "matched",
                "selected_tmdb_id": 157336,
                "file_path": "/movies/Interstellar.mkv"
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_movies.json"

            save_movies(movies, output_file)
            loaded_movies = load_movies(output_file)

            self.assertEqual(loaded_movies, movies)

class TestIdentifyMovie(unittest.TestCase):

    def test_identify_unique_match(self):
        local_movie = {
            "title": "The Dark Knight",
            "year": 2008
        }

        candidates = [
            {
                "tmdb_id": 155,
                "title": "The Dark Knight",
                "year": 2008
            },
            {
                "tmdb_id": 49026,
                "title": "The Dark Knight Rises",
                "year": 2012
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "matched")
        self.assertEqual(local_movie["selected_tmdb_id"], 155)

    def test_identify_multiple_candidates_without_year(self):
        local_movie = {
            "title": "King Kong",
            "year": None
        }
        candidates = [
            {"tmdb_id": 123, "title": "King Kong", "year": 1933},
            {"tmdb_id": 456, "title": "King Kong", "year": 2005}
        ]
        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "review")
        self.assertEqual(local_movie["candidates"], candidates)

    def test_identify_unmatched_movie(self):
        local_movie = {
            "title": "Interstellar",
            "year": 2014
        }

        candidates = [
            {"tmdb_id": 155, "title": "The Dark Knight", "year": 2008}
        ]
        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "unmatched")
        self.assertNotIn("selected_tmdb_id", local_movie)

    def test_identify_unique_candidate_without_year(self):
        local_movie = {
            "title": "Arrival",
            "year": None
        }

        candidates = [
            {
                "tmdb_id": 329865,
                "title": "Arrival",
                "year": 2016
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "review")
        self.assertEqual(local_movie["candidates"], candidates)
        self.assertNotIn("selected_tmdb_id", local_movie)


    def test_ignores_candidate_without_title(self):
        local_movie = {
            "title": "Interstellar",
            "year": 2014
        }

        candidates = [
            {
                "tmdb_id": 999,
                "year": 2014
            },
            {
                "tmdb_id": 157336,
                "title": "Interstellar",
                "year": 2014
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "matched")
        self.assertEqual(local_movie["selected_tmdb_id"], 157336)

    def test_ignores_candidate_without_year(self):
        local_movie = {
            "title": "Interstellar",
            "year": 2014
        }

        candidates = [
            {
                "tmdb_id": 999,
                "title": "Interstellar"
            },
            {
                "tmdb_id": 157336,
                "title": "Interstellar",
                "year": 2014
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "matched")
        self.assertEqual(local_movie["selected_tmdb_id"], 157336)


    def test_ignores_candidate_with_string_year(self):
        local_movie = {
            "title": "Interstellar",
            "year": 2014
        }

        candidates = [
            {
                "tmdb_id": 999,
                "title": "Interstellar",
                "year": "2014"
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "unmatched")

    def test_ignores_candidate_with_invalid_year(self):
        local_movie = {
            "title": "Interstellar",
            "year": 2014
        }

        candidates = [
            {
                "tmdb_id": 999,
                "title": "Interstellar",
                "year": 2500
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "unmatched")

    def test_identify_unique_candidate_when_both_years_are_unknown(self):
        local_movie = {
            "title": "Arrival",
            "year": None
        }

        candidates = [
            {
                "tmdb_id": 329865,
                "title": "Arrival",
                "year": None
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "review")
        self.assertEqual(local_movie["candidates"], candidates)
        self.assertNotIn("selected_tmdb_id", local_movie)

    def test_candidate_with_unknown_year_requires_review(self):
        local_movie = {
            "title": "Arrival",
            "year": 2016
        }

        candidates = [
            {
                "tmdb_id": 329865,
                "title": "Arrival",
                "year": None
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "review")
        self.assertEqual(local_movie["candidates"], candidates)
        self.assertNotIn("selected_tmdb_id", local_movie)

    def test_prefers_exact_year_over_unknown_year_candidate(self):
        local_movie = {
            "title": "Arrival",
            "year": 2016
        }

        candidates = [
            {
                "tmdb_id": 999,
                "title": "Arrival",
                "year": None
            },
            {
                "tmdb_id": 329865,
                "title": "Arrival",
                "year": 2016
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "matched")
        self.assertEqual(local_movie["selected_tmdb_id"], 329865)

    def test_review_includes_exact_and_unknown_year_candidates(self):
        local_movie = {
            "title": "Arrival",
            "year": 2016
        }

        candidates = [
            {
                "tmdb_id": 999,
                "title": "Arrival",
                "year": None
            },
            {
                "tmdb_id": 329865,
                "title": "Arrival",
                "year": 2016
            },
            {
                "tmdb_id": 472349,
                "title": "Arrival",
                "year": 2016
            }
        ]

        identify_movie(local_movie, candidates)

        self.assertEqual(local_movie["status"], "review")
        self.assertEqual(
            local_movie["candidates"],
            [
                candidates[1],
                candidates[2],
                candidates[0]
            ]
        )
        self.assertNotIn("selected_tmdb_id", local_movie)


class TestSaveSelection(unittest.TestCase):

    def test_save_selection(self):
        local_movie = {
            "title": "Arrival",
            "year": 2016,
            "status": "review"
        }

        selected_candidate = {
            "tmdb_id": 329865,
            "title": "Arrival",
            "year": 2016
        }

        save_selection(local_movie, selected_candidate)

        self.assertEqual(local_movie["selected_tmdb_id"], 329865)
        self.assertEqual(local_movie["status"], "matched")

    def test_save_selection_rejects_candidate_without_tmdb_id(self):
        local_movie = {
            "title": "Arrival",
            "year": 2016,
            "status": "review"
        }

        selected_candidate = {
            "title": "Arrival",
            "year": 2016
        }

        with self.assertRaisesRegex(
            ValueError,
            "Selected candidate must have a valid TMDB ID."
        ):
            save_selection(local_movie, selected_candidate)


    def test_save_selection_rejects_zero_tmdb_id(self):
        local_movie = {"status": "review"}
        selected_candidate = {"tmdb_id": 0}

        with self.assertRaises(ValueError):
            save_selection(local_movie, selected_candidate)


    def test_save_selection_rejects_boolean_tmdb_id(self):
        local_movie = {"status": "review"}
        selected_candidate = {"tmdb_id": True}

        with self.assertRaises(ValueError):
            save_selection(local_movie, selected_candidate)

    def test_save_selection_rejects_string_tmdb_id(self):
        local_movie = {"status": "review"}
        selected_candidate = {"tmdb_id": "329865"}

        with self.assertRaises(ValueError):
            save_selection(local_movie, selected_candidate)

class TestSelectCandidate(unittest.TestCase):

    def test_select_candidate_with_valid_choice(self):
        candidates = [
            {"tmdb_id": 100, "title": "Movie A"},
            {"tmdb_id": 200, "title": "Movie B"}
        ]

        result = select_candidate(candidates, "2")

        self.assertEqual(result, candidates[1])

    def test_select_candidate_rejects_non_numeric_choice(self):
        candidates = [{"tmdb_id": 100, "title": "Movie A"}]

        with self.assertRaises(ValueError):
            select_candidate(candidates, "abc")

    def test_select_candidate_rejects_out_of_range_choice(self):
        candidates = [{"tmdb_id": 100, "title": "Movie A"}]

        with self.assertRaises(ValueError):
            select_candidate(candidates, "2")

    def test_select_candidate_rejects_zero(self):
        candidates = [{"tmdb_id": 100, "title": "Movie A"}]

        with self.assertRaises(ValueError):
            select_candidate(candidates, "0")

    def test_select_candidate_with_empty_list(self):
        candidates = []

        with self.assertRaises(ValueError):
            select_candidate(candidates, "1")

    

class TestRemoveDuplicates(unittest.TestCase):

    def test_remove_duplicates_by_title_and_year(self):
        movies = [
            {"title": "The Dark Knight", "year": 2008, "file_path": "/movies/a.mkv"},
            {"title": "the.dark.knight", "year": 2008, "file_path": "/movies/b.mkv"},
            {"title": "The Dark Knight", "year": 2012, "file_path": "/movies/c.mkv"}
        ]

        result = remove_duplicates(movies)

        self.assertEqual(len(result), 2)

    def test_preserves_movies_with_unknown_year(self):
        movies = [
            {"title": "Crash", "year": None, "file_path": "/movies/a.mkv"},
            {"title": "Crash", "year": None, "file_path": "/movies/b.mkv"}
        ]

        result = remove_duplicates(movies)

        self.assertEqual(len(result), 2)


    def test_removes_duplicate_file_paths(self):
        movies = [
            {
                "title": "Interstellar",
                "year": 2014,
                "file_path": "/movies/interstellar.mkv"
            },
            {
                "title": "Different Title",
                "year": 2020,
                "file_path": "/movies/interstellar.mkv"
            }
        ]

        result = remove_duplicates(movies)

        self.assertEqual(len(result), 1)
class TestParseMovieFilename(unittest.TestCase):

    def test_filename_with_year_and_quality(self):
        result = parse_movie_filename(
            Path("The.Dark.Knight.2008.1080p.mkv")
        )

        self.assertEqual(result["title"], "The Dark Knight")
        self.assertEqual(result["year"], 2008)

    def test_filename_with_leading_number_and_no_year(self):
        result = parse_movie_filename(
            Path("2001 A Space Odyssey.mkv")
        )
        self.assertEqual(result["title"], "2001 A Space Odyssey")
        self.assertEqual(result["year"],None)

    def test_filename_with_parenthesized_year(self):
        result = parse_movie_filename(
            Path("Paris.Texas.(1984).mp4")
        )
        self.assertEqual(result["title"], "Paris Texas")
        self.assertEqual(result["year"], 1984)

    def test_filename_with_multiple_years(self):
        result = parse_movie_filename(
            Path("Movie.2020.Dreams.(2023).mkv")
        )

        self.assertEqual(result["title"], "Movie 2020 Dreams")
        self.assertEqual(result["year"], 2023)

    def test_filename_with_earliest_supported_year(self):
        result = parse_movie_filename(Path("Film.1888.mkv"))

        self.assertEqual(result["year"], 1888)

    def test_filename_with_latest_supported_year(self):
        result = parse_movie_filename(Path("Film.2100.mkv"))

        self.assertEqual(result["year"], 2100)

    def test_filename_without_year(self):
        result = parse_movie_filename(
            Path("The.Green.Knight.mkv")
        )

        self.assertEqual(result["title"], "The Green Knight")
        self.assertIsNone(result["year"])

class TestNormalizeTitle(unittest.TestCase):

    def test_normalize_title(self):
        result = normalize_title("The Dark Knight (2008)")
        self.assertEqual(result, "thedarkknight2008")

    def test_normalize_title_with_punctuation(self):
        result = normalize_title("Spider-Man: No Way Home")
        self.assertEqual(result, "spidermannowayhome")


class TestScanMovies(unittest.TestCase):

    def test_scans_video_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)

            (directory / "Interstellar.mkv").touch()
            (directory / "Inception.mp4").touch()
            (directory / "notes.txt").touch()

            movies = scan_movies(directory)

            self.assertEqual(len(movies), 2)

    def test_rejects_nonexistent_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir) / "missing"

            with self.assertRaises(FileNotFoundError):
                scan_movies(directory)

    def test_rejects_file_instead_of_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "movie.mkv"
            file_path.touch()

            with self.assertRaises(NotADirectoryError):
                scan_movies(file_path)


if __name__ == "__main__":
    unittest.main()
