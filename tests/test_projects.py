import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from api_integration import extract_report
from api_integration.extract_report import allowlisted, read_mock_pages, get_rows, ReportError
from book_adoption.etl import split_crn, old_term_code, run


class TestProjects(unittest.TestCase):
    def test_mock_reads_both_pages(self):
        self.assertEqual(len(read_mock_pages()), 3)

    def test_private_fields_are_not_exported(self):
        for record in allowlisted(read_mock_pages()):
            self.assertEqual(set(record), {"RecordID", "Category", "Status"})

    def test_rejects_bad_api_payload(self):
        with self.assertRaises(ReportError):
            get_rows({"DataRows": "not a list"})

    def test_live_flow_with_plain_text_token_and_pagination(self):
        """Simulate the live API: plain-text token, two data pages, then an empty page."""
        pages = iter([
            "eyJhbGciOi.fake.token",                                   # auth returns plain text
            '{"DataRows":[{"RecordID":"R1","Category":"A","Status":"Open","SSN":"x"}]}',
            '{"DataRows":[{"RecordID":"R2","Category":"B","Status":"Closed"}]}',
            '{"DataRows":[]}',
        ])
        seen = []

        def fake_urlopen(request, timeout=30):
            seen.append(request)
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = next(pages).encode("utf-8")
            return response

        with mock.patch.object(extract_report, "urlopen", side_effect=fake_urlopen):
            rows = extract_report.fetch_live("https://api.example.test/", "tenant", "key", "42")
        self.assertEqual([r["RecordID"] for r in rows], ["R1", "R2"])
        self.assertEqual(seen[1].get_header("Authorization"), "Bearer eyJhbGciOi.fake.token")
        self.assertNotIn("SSN", allowlisted(rows)[0])

    def test_course_reference(self):
        self.assertEqual(split_crn("12298|202610"), ("12298", "202610"))
        self.assertEqual(split_crn("18820"), ("18820", ""))
        self.assertEqual(split_crn("18820|26"), ("18820", ""))   # invalid term is ignored

    def test_old_term_mapping(self):
        self.assertEqual(old_term_code("J24"), "202420")
        self.assertEqual(old_term_code("G24"), "202510")

    def test_database_load(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = str(Path(temp) / "demo.sqlite")
            stats = run(db_path=destination)
            self.assertEqual(stats, {"feed_a": 3, "feed_b": 3, "loaded": 6})
            conn = sqlite3.connect(destination)
            try:
                rows = {r[0]: r[1:] for r in conn.execute(
                    "SELECT isbn, crn, term_code, new_price FROM book_adoption")}
            finally:
                conn.close()
            # compound reference split into CRN + term
            self.assertEqual(rows["9780000000001"], ("12298", "202610", "$120.00"))
            # ISBN keeps its leading zero; term comes from its own column; "New" price picked from a list
            self.assertEqual(rows["0306406152"], ("18820", "202620", "$89.50"))
            # no "New" price available -> blank, not an error
            self.assertEqual(rows["9780000000005"][2], "")
            # legacy term codes mapped (G = fall of the following year)
            self.assertEqual(rows["9780000000006"][1], "202510")
            self.assertEqual(rows["9780000000007"][1], "202530")

    def test_rejects_missing_identifier(self):
        with tempfile.TemporaryDirectory() as temp:
            bad = Path(temp) / "bad_b.csv"
            bad.write_text("term,department,course,section,ean13,title,author,publisher,new_price\n"
                           "J24,SCI,Biology,002,,No ISBN,Someone,Demo Books,$10.00\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                run(source_b=bad, db_path=str(Path(temp) / "x.sqlite"))


if __name__ == "__main__":
    unittest.main()

