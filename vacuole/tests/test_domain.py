import unittest

from vacuole.domain.ranking import button_options, dedupe, sort_products, within_price_range
from vacuole.tests.fakes import product


class RankingTests(unittest.TestCase):
    def test_price_ascending_puts_unpriced_last(self):
        items = [product("a", 300), product("b", None), product("c", 100)]
        self.assertEqual([p.title for p in sort_products(items, "price_asc")], ["c", "a", "b"])

    def test_rating_breaks_ties_with_review_count(self):
        items = [
            product("a", rating=4.5, reviews=10),
            product("b", rating=4.5, reviews=500),
            product("c", rating=3.0, reviews=9000),
        ]
        self.assertEqual([p.title for p in sort_products(items, "rating")], ["b", "a", "c"])

    def test_unknown_sort_falls_back_to_relevance(self):
        items = [product("ad", 10, sponsored=True), product("organic", 20)]
        self.assertEqual([p.title for p in sort_products(items, "nonsense")], ["organic", "ad"])

    def test_buttons_come_from_the_registry(self):
        self.assertEqual({o.key for o in button_options()}, {"price_asc", "rating"})


class DedupeTests(unittest.TestCase):
    def test_same_product_from_two_stores_merges_with_cheapest_first(self):
        a = product("Galaxy S24", 900, store="Flipkart")
        b = product("Galaxy  S24!", 800, store="Amazon")
        merged = dedupe([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].store, "Amazon")
        self.assertEqual(merged[0].offers[0]["store"], "Flipkart")

    def test_rows_without_link_are_dropped(self):
        self.assertEqual(dedupe([product("x", 1, link="")]), [])


class PriceRangeTests(unittest.TestCase):
    def test_bounds_apply_but_unpriced_rows_survive(self):
        items = [product("cheap", 50), product("ok", 150), product("dear", 900), product("na", None)]
        kept = within_price_range(items, 100, 500)
        self.assertEqual([p.title for p in kept], ["ok", "na"])


if __name__ == "__main__":
    unittest.main()
