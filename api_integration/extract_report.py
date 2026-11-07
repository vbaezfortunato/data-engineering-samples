"""Read a paginated report API and export only approved fields.

Mock mode reads local sample pages so the project runs without credentials.
"""
import argparse
import csv
import json
import os
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

FIELDS = ("RecordID", "Category", "Status")


class ReportError(Exception):
    pass


def get_rows(payload):
    if not isinstance(payload, dict):
        raise ReportError("Expected a JSON object")
    rows = payload.get("DataRows", payload.get("dataRows"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ReportError("Expected DataRows to be a list of objects")
    return rows


def allowlisted(rows):
    return [{key: str(row.get(key, "")) for key in FIELDS} for row in rows]


def read_mock_pages():
    folder = Path(__file__).resolve().parent / "samples"
    result = []
    for filename in ("page1.json", "page2.json"):
        result.extend(get_rows(json.loads((folder / filename).read_text(encoding="utf-8"))))
    return result


def request_json(url, *, method="GET", body=None, token=None):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some auth endpoints return the token as plain text rather than JSON.
        return text.strip()


def fetch_live(base_url, tenant_id, api_key, report_id, max_pages=100):
    root = base_url.rstrip("/") + "/"
    auth = request_json(urljoin(root, "auth/loginadmin"), method="POST",
                        body={"BEID": tenant_id, "WebServicesKey": api_key})
    # An API may return a JSON string or an object containing a token.
    token = auth if isinstance(auth, str) else auth.get("token") if isinstance(auth, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise ReportError("The authentication response did not include a token")
    rows = []
    for page in range(1, max_pages + 1):
        url = urljoin(root, f"reports/{quote(str(report_id), safe='')}?withData=true&page={page}")
        batch = get_rows(request_json(url, token=token))
        if not batch:
            return rows
        rows.extend(batch)
    raise ReportError("Page limit reached; report may be incomplete")


def export_csv(rows, destination):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(allowlisted(rows))
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Read synthetic sample pages")
    parser.add_argument("--output", default="output/report.csv")
    args = parser.parse_args()
    if args.mock:
        rows = read_mock_pages()
    else:
        required = ("API_BASE_URL", "API_TENANT_ID", "API_KEY", "API_REPORT_ID")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            parser.error("Missing environment variables: " + ", ".join(missing))
        rows = fetch_live(*(os.environ[name] for name in required))
    path = export_csv(rows, args.output)
    print(f"Exported {len(rows)} records to {path}")


if __name__ == "__main__":
    main()

