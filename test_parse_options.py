"""Unit tests for the description building in order_parser.

parse_options is a pure function of the Keeta `groups` list, so it can be exercised without a
browser, a network call or auth.json. Run with: python -m unittest test_parse_options
"""

import sys
import types
import unittest

# order_parser imports the runtime stack (requests/fastapi/uvicorn/playwright) at module level and
# those live only in the Docker image, not on a dev machine. The functions under test touch none of
# them, so stub the modules out rather than making the test suite drag in the whole runtime.
for _name in ("requests", "uvicorn"):
    sys.modules.setdefault(_name, types.ModuleType(_name))

_fastapi = types.ModuleType("fastapi")
_fastapi.FastAPI = lambda *args, **kwargs: types.SimpleNamespace(
    on_event=lambda *a, **k: (lambda fn: fn),
    get=lambda *a, **k: (lambda fn: fn),
)
sys.modules.setdefault("fastapi", _fastapi)

_playwright = types.ModuleType("playwright")
_playwright_sync = types.ModuleType("playwright.sync_api")
_playwright_sync.sync_playwright = lambda: None
sys.modules.setdefault("playwright", _playwright)
sys.modules.setdefault("playwright.sync_api", _playwright_sync)

from order_parser import addition_group, modifier_token, parse_options  # noqa: E402


def modifier_group(group_name, *modifiers):
    """A Keeta modifier group as it arrives in products[].groups."""
    return {
        "groupName": group_name,
        "shopProductGroupSkuList": [
            {"spuId": spu_id, "spuName": name, "count": count, "price": price}
            for spu_id, name, count, price in modifiers
        ],
    }


GARLIC_CRUST_GROUP = modifier_group("Garlic Crust", (85541299, "With Garlic Oil On The Crust", 1, 0))
THIN_DOUGH_GROUP = modifier_group("Dough Type", (85541300, "Thin", 1, 0))
MEDIUM_MODIFIERS_GROUP = modifier_group(
    "Modifiers For Medium Pizza",
    (85491655, "Cheddar", 1, 240),
    (85491656, "Darblu Cheese", 1, 240),
)


class ModifierTokenTest(unittest.TestCase):
    def test_omits_the_count_when_the_customer_took_one(self):
        self.assertEqual(modifier_token("Cheddar", 1), "Cheddar")

    def test_keeps_the_count_when_the_customer_took_more_than_one(self):
        self.assertEqual(modifier_token("Cheddar", 2), "Cheddar x2")

    def test_omits_the_count_when_it_is_missing(self):
        self.assertEqual(modifier_token("Cheddar", None), "Cheddar")


class AdditionGroupTest(unittest.TestCase):
    def test_wraps_the_names_in_the_addition_grammar(self):
        self.assertEqual(addition_group(["Cheddar", "Darblu Cheese"]), "+(Cheddar, Darblu Cheese)")

    def test_returns_an_empty_string_when_there_are_no_modifiers(self):
        self.assertEqual(addition_group([]), "")


class ParseOptionsNonComboTest(unittest.TestCase):
    def test_builds_the_addition_group_from_the_modifiers(self):
        result = parse_options([MEDIUM_MODIFIERS_GROUP], is_combo=False, size="M")

        self.assertEqual(result["description"], "+(Cheddar, Darblu Cheese)")

    def test_sets_the_crust_and_dough_flags_without_echoing_them_into_the_description(self):
        result = parse_options(
            [GARLIC_CRUST_GROUP, THIN_DOUGH_GROUP, MEDIUM_MODIFIERS_GROUP], is_combo=False, size="M"
        )

        self.assertTrue(result["is_garlic_crust"])
        self.assertTrue(result["is_thin_dough"])
        self.assertEqual(result["description"], "+(Cheddar, Darblu Cheese)")

    def test_leaves_the_description_empty_when_no_modifier_was_chosen(self):
        result = parse_options([GARLIC_CRUST_GROUP], is_combo=False, size="M")

        self.assertEqual(result["description"], "")

    def test_collects_better_together_items_as_separate_order_items(self):
        group = modifier_group("Better Together", (85491700, "Garlic Sauce", 1, 500))

        result = parse_options([group], is_combo=False, size="M")

        self.assertEqual(len(result["order_items"]), 1)
        self.assertEqual(result["order_items"][0]["name"], "Garlic Sauce")


class ParseOptionsComboTest(unittest.TestCase):
    def test_gives_each_pizza_child_the_addition_group(self):
        groups = [
            modifier_group("Choose Your Pizza", (97384131, "Pepperoni", 1, 0)),
            modifier_group("Choose Your Beverage", (97384132, "Pepsi", 1, 0)),
            MEDIUM_MODIFIERS_GROUP,
        ]

        result = parse_options(groups, is_combo=True, size="M")

        pizza = next(item for item in result["combo_items"] if item["category"] == "Pizzas")
        self.assertEqual(pizza["description"], "+(Cheddar, Darblu Cheese)")

    def test_does_not_echo_the_crust_choice_into_the_child_description(self):
        groups = [
            modifier_group("Choose Your Pizza", (97384131, "Pepperoni", 1, 0)),
            MEDIUM_MODIFIERS_GROUP,
            GARLIC_CRUST_GROUP,
        ]

        result = parse_options(groups, is_combo=True, size="M")

        pizza = next(item for item in result["combo_items"] if item["category"] == "Pizzas")
        self.assertEqual(pizza["description"], "+(Cheddar, Darblu Cheese)")


if __name__ == "__main__":
    unittest.main()
