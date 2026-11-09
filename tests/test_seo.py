"""Offline checks for canonical discovery, visible identity and linked data."""
import html.parser
import json
import re
import unittest
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "website"
ORIGIN = "https://agents-collab.com"
ROUTES = ("", "guide/", "research/", "experiments/", "story/")


class Page(html.parser.HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.links, self.meta, self.ld, self.text = [], {}, [], []
        self.in_ld = False
        self.in_script = False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link":
            self.links.append(attrs)
        if tag == "meta":
            self.meta[attrs.get("name", attrs.get("property"))] = attrs.get("content")
        if tag == "script":
            self.in_script = True
            self.in_ld = attrs.get("type") == "application/ld+json"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = self.in_ld = False

    def handle_data(self, data):
        if self.in_ld:
            self.ld.append(json.loads(data))
        elif not self.in_script:
            self.text.append(data)


class Discovery(unittest.TestCase):
    def test_all_indexable_pages_have_consistent_canonical_and_social_metadata(self):
        descriptions = set()
        for route in ROUTES:
            with self.subTest(route=route):
                page = Page((SITE / route / "index.html").read_text())
                url = ORIGIN + "/" + route
                self.assertEqual([p["href"] for p in page.links if p.get("rel") == "canonical"], [url])
                self.assertEqual(page.meta["og:url"], url)
                self.assertNotIn("noindex", page.meta["robots"])
                self.assertTrue(page.meta["description"])
                self.assertEqual(page.meta["og:description"], page.meta["description"])
                self.assertEqual(page.meta["twitter:description"], page.meta["description"])
                descriptions.add(page.meta["description"])
                image = urllib.parse.urlsplit(page.meta["og:image"])
                self.assertEqual(image.netloc, "agents-collab.com")
                self.assertTrue((SITE / image.path.lstrip("/")).is_file())
        self.assertEqual(len(descriptions), len(ROUTES))

    def test_linked_data_matches_visible_project_identity_and_canonical_page(self):
        for route in ROUTES:
            with self.subTest(route=route):
                page = Page((SITE / route / "index.html").read_text())
                self.assertEqual(len(page.ld), 1)
                document = page.ld[0]
                self.assertEqual(document["@context"], "https://schema.org")
                graph = {node["@id"]: node for node in document["@graph"]}
                url = ORIGIN + "/" + route
                current = graph[url + "#page"]
                self.assertEqual(current["url"], url)
                self.assertEqual(current["description"], page.meta["description"])
                creator = graph[ORIGIN + "/#creator"]
                self.assertIn(creator["name"], " ".join(page.text))
                self.assertIn(current["dateModified"], (SITE / route / "index.html").read_text())
                source = graph[ORIGIN + "/#project"]
                self.assertEqual(source["codeRepository"], "https://github.com/jaredchu/agents-collab")
                self.assertEqual(source["license"], source["codeRepository"] + "/blob/main/LICENSE")
                self.assertNotIn("aggregateRating", source)
                self.assertNotIn("offers", source)
                if route:
                    crumbs = graph[current["breadcrumb"]["@id"]]["itemListElement"]
                    self.assertEqual([x["item"] for x in crumbs], [ORIGIN + "/", url])
                    self.assertIn('class="breadcrumb"', (SITE / route / "index.html").read_text())

    def test_robots_and_sitemap_discover_exactly_the_canonical_pages(self):
        expected = {ORIGIN + "/" + route for route in ROUTES}
        robots = urllib.robotparser.RobotFileParser()
        robots.parse((SITE / "robots.txt").read_text().splitlines())
        self.assertEqual(robots.site_maps(), [ORIGIN + "/sitemap.xml"])
        for agent in ("Googlebot", "OAI-SearchBot", "GPTBot"):
            self.assertTrue(all(robots.can_fetch(agent, url) for url in expected))
        root = ET.fromstring((SITE / "sitemap.xml").read_bytes())
        urls = [n.text for n in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        self.assertEqual(set(urls), expected)
        self.assertEqual(len(urls), len(expected))
        self.assertFalse(any("index.html" in url or "pages.dev" in url for url in urls))

    def test_ai_navigation_map_matches_pages_and_keeps_evidence_limits(self):
        manifest = json.loads((SITE / "manifest.json").read_text())
        urls = {page["url"] for page in manifest["pages"]}
        self.assertEqual(urls, {ORIGIN + "/" + route for route in ROUTES})
        self.assertEqual(manifest["evidence"]["results"], ORIGIN + "/experiments/")
        self.assertTrue(manifest["evidence"]["limits"])
        llms = (SITE / "llms.txt").read_text()
        self.assertTrue(all(url in llms for url in urls))
        self.assertIn("not an access rule", llms)
        self.assertNotIn("guaranteed citations", llms)

    def test_static_host_has_real_404_document_and_bounded_asset_cache_policy(self):
        page = Page((SITE / "404.html").read_text())
        self.assertIn("noindex", page.meta["robots"])
        headers = (SITE / "_headers").read_text()
        self.assertIn("/assets/*", headers)
        self.assertIn("max-age=3600", headers)
        self.assertNotIn("immutable", headers)  # these asset names are not content-hashed
        self.assertIn("/downloads/*", headers)
        self.assertIn("must-revalidate", headers)


if __name__ == "__main__":
    unittest.main()
