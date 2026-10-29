import gzip
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "site"))
import botcheck  # noqa: E402

GPTBOT_UA = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)"
CLAUDE_UA = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"
GOOGLE_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
HUMAN_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def line(ua, size=1000, ts="29/Oct/2026:10:00:00 +0000", path="/docs/intro"):
    return f'203.0.113.7 - - [{ts}] "GET {path} HTTP/1.1" 200 {size} "-" "{ua}"'


SAMPLE = [
    line(GPTBOT_UA, 4000, "01/Oct/2026:00:00:00 +0000"),
    line(GPTBOT_UA, 4000),
    line(CLAUDE_UA, 2000),
    line(GOOGLE_UA, 1000),
    line(HUMAN_UA, 500),
    line(HUMAN_UA, 500, "11/Oct/2026:00:00:00 +0000"),
    "garbage that is not a log line",
]


class ParseLineTest(unittest.TestCase):
    def test_combined_format(self):
        rec = botcheck.parse_line(line(GPTBOT_UA, 1234))
        self.assertEqual(rec["bytes"], 1234)
        self.assertEqual(rec["ua"], GPTBOT_UA)
        self.assertEqual(rec["time"].year, 2026)

    def test_dash_bytes_is_zero(self):
        rec = botcheck.parse_line(line(HUMAN_UA).replace(" 200 1000 ", " 304 - "))
        self.assertEqual(rec["bytes"], 0)

    def test_escaped_quote_in_request(self):
        rec = botcheck.parse_line(line(HUMAN_UA, path='/search?q=\\"x\\"'))
        self.assertIsNotNone(rec)
        self.assertEqual(rec["ua"], HUMAN_UA)

    def test_unparseable(self):
        self.assertIsNone(botcheck.parse_line("nope"))
        self.assertIsNone(botcheck.parse_line(""))


class ClassifyTest(unittest.TestCase):
    def test_ai(self):
        self.assertEqual(botcheck.classify(GPTBOT_UA), ("ai", "GPTBot", "OpenAI"))
        self.assertEqual(botcheck.classify(CLAUDE_UA), ("ai", "ClaudeBot", "Anthropic"))

    def test_case_insensitive(self):
        self.assertEqual(botcheck.classify("meta-ExternalAgent/1.1")[1], "meta-externalagent")

    def test_search(self):
        self.assertEqual(botcheck.classify(GOOGLE_UA)[0], "search")

    def test_other(self):
        self.assertEqual(botcheck.classify(HUMAN_UA), ("other", None, None))


class AnalyzeTest(unittest.TestCase):
    def setUp(self):
        self.report = botcheck.analyze(SAMPLE)

    def test_totals(self):
        r = self.report
        self.assertEqual(r["skipped"], 1)
        self.assertEqual(r["total"], {"requests": 6, "bytes": 12000})
        self.assertEqual(r["kinds"]["ai"], {"requests": 3, "bytes": 10000})
        self.assertEqual(r["kinds"]["search"], {"requests": 1, "bytes": 1000})
        self.assertEqual(r["kinds"]["other"], {"requests": 2, "bytes": 1000})

    def test_bots_sorted_by_bytes(self):
        bots = self.report["bots"]
        self.assertEqual([b["bot"] for b in bots], ["GPTBot", "ClaudeBot"])
        self.assertEqual(bots[0]["requests"], 2)
        self.assertEqual(bots[0]["bytes"], 8000)

    def test_span_days(self):
        self.assertAlmostEqual(self.report["span_days"], 28.4167, places=3)

    def test_cost(self):
        cost = botcheck.estimate_cost(self.report, price_per_gb=0.15)
        self.assertAlmostEqual(cost["period"], 10000 / 1e9 * 0.15)
        self.assertAlmostEqual(cost["monthly"], cost["period"] / self.report["span_days"] * 30)

    def test_no_monthly_for_short_span(self):
        report = botcheck.analyze([line(GPTBOT_UA), line(GPTBOT_UA)])
        self.assertIsNone(botcheck.estimate_cost(report, 0.15)["monthly"])


class MainTest(unittest.TestCase):
    def run_main(self, args):
        out = io.StringIO()
        with redirect_stdout(out):
            botcheck.main(args)
        return out.getvalue()

    def test_reads_gzip_and_plain(self):
        with tempfile.TemporaryDirectory() as d:
            plain = os.path.join(d, "access.log")
            gz = os.path.join(d, "access.log.1.gz")
            with open(plain, "w") as f:
                f.write("\n".join(SAMPLE[:3]) + "\n")
            with gzip.open(gz, "wt") as f:
                f.write("\n".join(SAMPLE[3:]) + "\n")
            data = json.loads(self.run_main([plain, gz, "--json"]))
        self.assertEqual(data["total"]["requests"], 6)
        self.assertEqual(data["skipped"], 1)
        self.assertIn("cost", data)

    def test_text_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "access.log")
            with open(path, "w") as f:
                f.write("\n".join(SAMPLE) + "\n")
            out = self.run_main([path])
        self.assertIn("GPTBot", out)
        self.assertIn("83.3%", out)
        self.assertIn(botcheck.SITE_URL, out)


if __name__ == "__main__":
    unittest.main()
