"""Combine two synthetic book adoption feeds into a local SQLite database."""
import argparse
import csv
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ("source", "term_code", "department", "course", "section",
          "crn", "isbn", "title", "author", "publisher", "new_price")
PRICE = re.compile(r"(?i)(?:^|[,;| ])New\s*:\s*(\$?\d+(?:\.\d{1,2})?)")


def split_crn(raw):
    parts = (raw or "").split("|", 1)
    crn = parts[0].strip()
    term = parts[1].strip() if len(parts) == 2 else ""
    return crn, term if re.fullmatch(r"\d{6}", term) else ""


def old_term_code(raw):
    match = re.fullmatch(r"([JSBG])(\d{2})", (raw or "").upper().strip())
    if not match:
        return ""
    prefix, year = match.groups()
    year = 2000 + int(year) + (prefix == "G")
    suffix = {"J": "20", "S": "20", "B": "30", "G": "10"}[prefix]
    return f"{year}{suffix}"


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def normalize_a(row):
    crn, term = split_crn(row["course_crn"])
    if not term:
        term = row.get("term_code", "")
    match = PRICE.search(row.get("sales_prices", ""))
    return ("A", term, row["department"], row["course"], row["section"],
            crn, row["isbn"], row["title"], row["author"], row["publisher"],
            match.group(1) if match else "")


def normalize_b(row):
    return ("B", old_term_code(row["term"]), row["department"],
            row["course"], row["section"], "", row["ean13"], row["title"],
            row["author"], row["publisher"], row["new_price"])


def run(source_a=None, source_b=None, db_path="book_adoption_demo.sqlite"):
    source_a = Path(source_a) if source_a else ROOT / "samples" / "vendor_a.csv"
    source_b = Path(source_b) if source_b else ROOT / "samples" / "vendor_b.csv"
    first = [normalize_a(row) for row in read_rows(source_a)]
    second = [normalize_b(row) for row in read_rows(source_b)]
    rows = first + second
    if any(not row[1] or not row[6] for row in rows):
        raise ValueError("A record has no valid term code or book identifier")
    connection = sqlite3.connect(db_path)
    try:
        columns = ", ".join(f"{field} TEXT" for field in FIELDS)
        connection.execute(f"CREATE TABLE IF NOT EXISTS book_adoption ({columns})")
        with connection:
            connection.execute("DELETE FROM book_adoption")
            connection.executemany(
                f"INSERT INTO book_adoption VALUES ({','.join('?' for _ in FIELDS)})", rows)
        count = connection.execute("SELECT COUNT(*) FROM book_adoption").fetchone()[0]
        if count != len(rows):
            raise RuntimeError("Loaded record count does not match the input")
        return {"feed_a": len(first), "feed_b": len(second), "loaded": count}
    finally:
        connection.close()


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--db", default="book_adoption_demo.sqlite")
    args = cli.parse_args()
    print(run(db_path=args.db))

