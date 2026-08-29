from html.parser import HTMLParser
from pathlib import Path
import unittest


PUBLIC = Path(__file__).parents[1] / "public"


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_links = []
        self.buttons = {}
        self.pagination_links = []
        self.see_also_links = []
        self._in_pagination = False
        self._in_see_also = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "nav" and attributes.get("aria-label") == "Posts pagination":
            self._in_pagination = True
        if tag == "section" and "see-also" in (attributes.get("class") or "").split():
            self._in_see_also = True
        if tag == "a" and attributes.get("aria-current") == "page":
            self.current_links.append(attributes.get("href"))
        if tag == "button" and attributes.get("id"):
            self.buttons[attributes["id"]] = attributes
        if tag == "a" and self._in_pagination:
            self.pagination_links.append(attributes)
        if tag == "a" and self._in_see_also:
            self.see_also_links.append(attributes.get("href"))

    def handle_endtag(self, tag):
        if tag == "nav" and self._in_pagination:
            self._in_pagination = False
        if tag == "section" and self._in_see_also:
            self._in_see_also = False


def parse(relative_path):
    parser = NavigationParser()
    parser.feed((PUBLIC / relative_path).read_text())
    return parser


class SiteNavigationTests(unittest.TestCase):
    def test_primary_navigation_marks_the_current_destination(self):
        pages = {
            "about/index.html": "/about/",
            "posts/daily/slice-patterns/index.html": "/posts/",
            "tags/index.html": "/tags/",
        }
        for page, expected in pages.items():
            with self.subTest(page=page):
                self.assertEqual(parse(page).current_links, [expected])

    def test_icon_controls_are_named_buttons(self):
        parser = parse("posts/index.html")
        menu = parser.buttons["navigation-toggle"]
        colour_scheme = parser.buttons["dark-mode-toggle"]

        self.assertEqual(menu.get("type"), "button")
        self.assertEqual(menu.get("aria-controls"), "primary-navigation")
        self.assertEqual(menu.get("aria-expanded"), "false")
        self.assertEqual(colour_scheme.get("type"), "button")
        self.assertTrue(colour_scheme.get("aria-label"))

    def test_archive_exposes_directional_pagination(self):
        parser = parse("posts/index.html")
        next_links = [link for link in parser.pagination_links if link.get("rel") == "next"]
        self.assertEqual(len(next_links), 1)

    def test_series_articles_link_to_other_installments(self):
        parser = parse("posts/working-with-gcode/index.html")

        self.assertIn("/posts/wiring-up-communication/", parser.see_also_links)
        self.assertIn("/posts/a-better-frontend/", parser.see_also_links)
        self.assertNotIn("/posts/working-with-gcode/", parser.see_also_links)


if __name__ == "__main__":
    unittest.main()
