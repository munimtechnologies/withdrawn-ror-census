# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. Made with AI agents working in MV2's name.
"""Offline tests for withdrawn_ror_census (no network)."""
import unittest

import withdrawn_ror_census as w


def row(rid, v116, dc_post=0, zen_post=0, cr_post=0, years=(0, 0, 0, 0),
        succ="", vocab="withdrawn", above_s=""):
    r = {"id": rid, "name": rid, "v116_status": v116, "successors": succ,
         "dc_post": dc_post, "zen_post": zen_post, "cr_post": cr_post,
         "zen_vocab": vocab, "zen_above_successor": above_s, "error": ""}
    for y, n in zip(w.POST_YEARS, years):
        r["dc_%d" % y] = n
    return r


class TestParsing(unittest.TestCase):
    def test_short_ror(self):
        self.assertEqual(w.short_ror("https://ror.org/03wevmz92"), "03wevmz92")
        self.assertEqual(w.short_ror("03WEVMZ92"), "03wevmz92")
        self.assertEqual(w.short_ror("edmo:3800"), "")
        self.assertEqual(w.short_ror(None), "")

    def test_parse_ror_v2(self):
        item = {"id": "https://ror.org/03wevmz92", "status": "withdrawn",
                "names": [{"value": "HMS", "types": ["acronym"]},
                          {"value": "Harvard Medical School",
                           "types": ["ror_display", "label"]}],
                "relationships": [
                    {"type": "related", "id": "https://ror.org/05xckek43"},
                    {"type": "successor", "id": "https://ror.org/03vek6s52"},
                    {"type": "parent", "id": "https://ror.org/03vek6s52"}]}
        p = w.parse_ror_v2(item)
        self.assertEqual(p["id"], "03wevmz92")
        self.assertEqual(p["name"], "Harvard Medical School")
        self.assertEqual(p["status"], "withdrawn")
        self.assertEqual(p["successors"], ["03vek6s52"])
        self.assertEqual(p["parents"], ["03vek6s52"])

    def test_statuses_from_records(self):
        recs = [{"id": "https://ror.org/03wevmz92", "status": "withdrawn"},
                {"id": "https://ror.org/03vek6s52", "status": "active"},
                {"id": "not-a-ror", "status": "active"}]
        self.assertEqual(w.statuses_from_records(recs),
                         {"03wevmz92": "withdrawn", "03vek6s52": "active"})

    def test_datacite_query(self):
        q = w.datacite_query("03wevmz92")
        self.assertIn('creators.affiliation.affiliationIdentifier:"https://ror.org/03wevmz92"', q)
        self.assertIn('fundingReferences.funderIdentifier:"https://ror.org/03wevmz92"', q)
        self.assertEqual(q.count(" OR "), 2)

    def test_clean_query(self):
        self.assertEqual(w.clean_query("BAE Systems Electronic Systems (United States)"),
                         "BAE Systems Electronic Systems United States")
        self.assertEqual(w.clean_query("Akademia Wychowania Fizycznego we Wrocławiu"),
                         "Akademia Wychowania Fizycznego we Wrocławiu")

    def test_rank_and_above(self):
        hits = [{"id": "03wevmz92"}, {"id": "edmo:3800"}, {"id": "03vek6s52"},
                {"id": "x", "identifiers": [{"scheme": "ror", "identifier": "012345678"}]}]
        self.assertEqual(w.rank_in_hits(hits, "03wevmz92"), 1)
        self.assertEqual(w.rank_in_hits(hits, "03vek6s52"), 3)
        self.assertEqual(w.rank_in_hits(hits, "012345678"), 4)
        self.assertIsNone(w.rank_in_hits(hits, "0abcdefgh"))
        self.assertTrue(w.above(1, 5))
        self.assertTrue(w.above(1, None))
        self.assertFalse(w.above(None, 3))
        self.assertFalse(w.above(4, 2))


class TestSummary(unittest.TestCase):
    def test_summarize(self):
        rows = [row("01", "withdrawn", 2000, 1800, 300, (100, 400, 600, 900), "a", "withdrawn", "1"),
                row("02", "withdrawn", 1200, 600, 0, (200, 300, 300, 400), "", "withdrawn", "0"),
                row("03", "withdrawn", vocab="absent"),
                row("04", "active", 5000, 5000, 0, (0, 0, 0, 5000), "b", "withdrawn", "1")]
        s = w.summarize(rows)
        m, p = s["metrics"], s["predictions"]
        self.assertEqual(m["n_w1"], 3)
        self.assertEqual(m["w1_used_dc_post"], 2)
        self.assertEqual(m["w1_dc_post_pairs"], 3200)
        self.assertEqual(m["w1_zen_post_pairs"], 2400)
        self.assertEqual(m["w1_cr_post_pairs"], 300)
        self.assertEqual(m["w1_dc_post_by_year"], {"2023": 300, "2024": 700, "2025": 900, "2026": 1300})
        self.assertAlmostEqual(m["zen_share"], 0.75)
        self.assertAlmostEqual(m["succ_share_used_any"], 0.5)
        self.assertAlmostEqual(m["vocab_withdrawn_share"], 0.75)
        self.assertEqual(m["n_big_zen"], 2)
        self.assertAlmostEqual(m["big_above_share"], 0.5)
        self.assertEqual(m["all_dc_post_pairs"], 8200)
        self.assertEqual(m["top"][0]["id"], "01")
        self.assertFalse(p["P2_60_to_500_w1_ids_used"])
        self.assertTrue(p["P3_ge_3000_dc_pairs"])
        self.assertTrue(p["P4_zenodo_share_ge_60pct"])
        self.assertTrue(p["P5_2025_ge_3x_2023"])
        self.assertTrue(p["P6_crossref_lt_half_datacite"])
        self.assertFalse(p["P7_ge_80pct_used_have_successor"])
        self.assertFalse(p["P8_ge_95pct_in_zenodo_vocab_withdrawn"])
        self.assertTrue(p["P9_ge_half_big_rank_above_successor"])

    def test_summarize_empty(self):
        s = w.summarize([])
        self.assertFalse(s["predictions"]["P4_zenodo_share_ge_60pct"])
        self.assertIsNone(s["metrics"]["zen_share"])

    def test_sanity(self):
        h = row(w.SANITY_HMS, "withdrawn", 1131, 1000, 220, (42, 275, 362, 452),
                w.SANITY_HMS_SUCCESSOR, "withdrawn", "1")
        h.update({"dc_total": 1209, "cr_total": 237, "zen_rank": 1})
        c = w.sanity([h])["checks"]
        self.assertTrue(c["hms_w1"])
        self.assertTrue(c["hms_dc_total_ge_1150"])
        self.assertTrue(c["hms_zen_post_ge_950"])
        self.assertTrue(c["hms_cr_total_ge_220"])
        self.assertTrue(c["hms_zen_rank_1"])
        self.assertTrue(c["hms_successor_harvard"])
        self.assertTrue(c["hms_years_sum_eq_post"])
        self.assertFalse(c["n_withdrawn_ge_1400"])
        self.assertFalse(w.sanity([h])["all_pass"])


if __name__ == "__main__":
    unittest.main()
