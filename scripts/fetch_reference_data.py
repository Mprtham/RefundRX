"""One-time download of real, public, non-personal reference lists into reference/.

- Drugs: NHSBSA English Prescribing Dataset (EPD, open data, OGL). BNF codes and
  descriptions at presentation level, with national item counts used as a
  realistic frequency weight. Used for context on the prescription line only.
- Pharmacies: NHS ODS ORD API, PrimaryRoleId RO182 (pharmacy). Only the
  organisation name and the OUTWARD postcode are kept — never a full postcode.

The results are committed, so the generator never needs network access.
Run:  python -m scripts.fetch_reference_data
"""
import csv
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference"

EPD_MONTH = "EPD_202506"
EPD_URL = "https://opendata.nhsbsa.net/api/3/action/datastore_search_sql"
ODS_URL = "https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations"


def fetch_drugs(limit: int = 200) -> None:
    sql = (
        f"SELECT BNF_CODE, BNF_DESCRIPTION, SUM(ITEMS) AS items FROM `{EPD_MONTH}` "
        f"GROUP BY BNF_CODE, BNF_DESCRIPTION ORDER BY items DESC LIMIT {limit}"
    )
    resp = httpx.get(EPD_URL, params={"resource_id": EPD_MONTH, "sql": sql}, timeout=300)
    resp.raise_for_status()
    records = resp.json()["result"]["result"]["records"]
    with open(REF / "drugs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["drug_name", "bnf_code", "weight"])
        for r in records:
            w.writerow([r["BNF_DESCRIPTION"].strip(), r["BNF_CODE"], int(r["items"])])
    print(f"drugs.csv: {len(records)} rows from {EPD_MONTH}")


def fetch_pharmacies(limit: int = 400) -> None:
    resp = httpx.get(
        ODS_URL,
        params={"PrimaryRoleId": "RO182", "Status": "Active", "Limit": limit},
        timeout=60,
    )
    resp.raise_for_status()
    orgs = resp.json()["Organisations"]
    seen = set()
    rows = []
    for o in orgs:
        outward = (o.get("PostCode") or "").split(" ")[0]
        key = (o["Name"], outward)
        if outward and key not in seen:
            seen.add(key)
            rows.append(key)
    with open(REF / "pharmacies.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pharmacy_name", "postcode_outward"])
        w.writerows(rows)
    print(f"pharmacies.csv: {len(rows)} rows from NHS ODS (RO182)")


if __name__ == "__main__":
    REF.mkdir(exist_ok=True)
    fetch_drugs()
    fetch_pharmacies()
