# Data provenance

**Real (public, non-personal):**

- **Drug names and BNF codes** (`reference/drugs.csv`) come from the NHSBSA English Prescribing Dataset (EPD), June 2025. It is open data under the OGL. The BNF descriptions are aligned to dm+d. We used EPD instead of the raw dm+d release because dm+d needs a TRUD login. National item counts are used as frequency weights. Each drug is incidental context on the prescription line and is never a decision input.
- **Pharmacy names** (`reference/pharmacies.csv`) come from the NHS ODS ORD API with role RO182 (pharmacy). The ODS register is the source behind data.gov.uk's pharmacy listings. Only the **outward** postcode is kept (for example `SK7`), never a full postcode.
- **Exemption categories and the prescription charge** (`reference/exemption_categories.csv`) are age, maternity, medical and HC2, with the £9.90 charge. They follow NHSBSA/NHS England public guidance. PPC and HC3 are deliberately absent because they are out of scope. The category weights are rough plausibility weights, not official shares.
- **Policy text** (`policy_docs/fp57_guidance.md`) is a paraphrased summary of public NHSBSA guidance. It is used for citation only, and `policy_rules` is the sole decision authority.

**Fabricated:**

- Everything in `data/synthetic_patients.csv` and `data/synthetic_claims.csv`: names (Faker `en_GB`), dates of birth, patient IDs, FP57 form references, payment and claim dates. Patient IDs use NHS Digital's 999-prefixed test range, which is never valid for a real patient. No real person's data is used, so no data subject exists.

Regenerate with `python -m scripts.fetch_reference_data` (network) and `python -m scripts.generate_synthetic_data` (offline, seeded).
