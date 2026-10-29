# HOAS — Hospital Outpatient Appointment System (Group 05)

Course project: CSE703095 Software Requirements, Phenikaa University (2026).

This repository contains the requirements workbook, an educational in-memory Python prototype, use-case and test-case catalogues, and a small test suite. The data and scenarios are synthetic. This is **not** a deployed hospital application and does not demonstrate clinical or production security acceptance.

## Repository contents

- `HOAS_Requirements_Management_Group05.xlsx` — requirements and traceability workbook.
- `src/` — prototype model and use-case/test-case catalogue models.
- `data/` — synthetic project dataset and traceability data.
- `tests/` — automated prototype and specification consistency tests.
- `scripts/` — regenerate the Markdown/CSV specification exports.
- `docs/` — short project overview.
- `generated_specifications/` — created by the generator; not required to be committed.

## Requirements

Python 3.10 or newer. No third-party Python packages are required.

## Run checks

From the repository root:

```bash
python -m unittest discover -s tests -v
python scripts/generate_specifications.py
```

On Windows, `py -3` may be used instead of `python`.

## Scope note

Automated tests exercise only an in-memory educational prototype and specification data. They are not tests of a live hospital system, clinical workflows, production security, performance, or real notification delivery.
