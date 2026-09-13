import unittest

import pandas as pd

from recommender import build_model, recommend_movies


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.movies = pd.DataFrame(
            {
                "title": ["Space Story", "Space Mission", "Cooking Show"],
                "genres": ["Sci-Fi|Drama", "Sci-Fi|Adventure", "Comedy"],
                "keywords": ["space mission", "space astronaut", "food kitchen"],
                "overview": ["A space journey", "An astronaut travels", "A chef cooks"],
                "cast": ["Actor A", "Actor B", "Actor C"],
                "director": ["Director A", "Director B", "Director C"],
            }
        )
        self.movies["combined_text"] = self.movies[
            ["genres", "keywords", "overview", "cast", "director"]
        ].agg(" ".join, axis=1)
        _, self.vectors = build_model(self.movies)

    def test_similar_movie_is_ranked_first_and_selected_movie_is_removed(self):
        results = recommend_movies(self.movies, self.vectors, ["Space Story"], 2)
        self.assertEqual(results.iloc[0]["title"], "Space Mission")
        self.assertNotIn("Space Story", results["title"].tolist())

    def test_unknown_selection_returns_empty_results(self):
        results = recommend_movies(self.movies, self.vectors, ["Missing Movie"])
        self.assertTrue(results.empty)

    def test_default_results_include_every_positive_match(self):
        results = recommend_movies(self.movies, self.vectors, ["Space Story"])
        self.assertEqual(results.iloc[0]["title"], "Space Mission")
        self.assertEqual(len(results), 2)
        self.assertTrue((results["similarity_score"] > 0).all())


if __name__ == "__main__":
    unittest.main()