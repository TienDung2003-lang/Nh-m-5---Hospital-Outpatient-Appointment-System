"""Regenerate English use case, test case and traceability exports from HOAS data.

Run: python scripts/generate_specifications.py
Standard library only.
"""
import sys,csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.use_cases import load_catalog as use_cases,validate_catalog as check_ucs,DATA_PATH
from src.test_cases import load_catalog as test_cases,validate_catalog as check_tcs

OUT=ROOT/'generated_specifications'
OUT.mkdir(exist_ok=True)
D=json.loads(DATA_PATH.read_text(encoding='utf-8'))
check_ucs();check_tcs()
ucs=use_cases();tests=test_cases()

(OUT/'USE_CASE_SPECIFICATIONS.md').write_text('# HOAS - Use Case Specifications (English)\n\n'
  +'Source of truth: `data/hoas_dataset.json`. This is a case-study specification, not evidence of hospital approval.\n\n'
  +'\n\n'.join(case.as_markdown() for case in ucs.values())+'\n',encoding='utf-8')
(OUT/'TEST_CASE_SPECIFICATIONS.md').write_text('# HOAS - Test Case Specifications (English)\n\n'
  +'These 50 catalogue cases are designed for a hypothetical hospital system. Prototype execution evidence is separately recorded in `evidence/`.\n\n'
  +'\n\n'.join(tc.as_markdown() for tc in tests.values())+'\n',encoding='utf-8')

with (OUT/'USE_CASE_REGISTER.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['UC ID','Title','Primary Actor','Secondary Actor','Preconditions','Success Postconditions','Failure Postconditions','Priority','Main Flow Steps','Extensions','NFR Links'])
 for uc in ucs.values():
  w.writerow([uc.id,uc.title,uc.actor,uc.secondary,uc.preconditions,uc.success_postconditions,uc.failure_postconditions,uc.priority,' | '.join(uc.main_steps),' | '.join(e['ref']+' '+e['condition']+': '+e['response'] for e in uc.extensions),'; '.join(uc.nfr_links)])

with (OUT/'TEST_CASE_REGISTER.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['TC ID','UC ID','Requirement ID','Case Name','Case Type','Preconditions','Test Steps','Input Data','Expected Result','Real Hospital Execution Status'])
 for tc in tests.values():w.writerow([tc.id,tc.use_case_id,tc.requirement,tc.name,tc.kind,tc.preconditions,tc.steps,tc.input_data,tc.expected_result,'Not executed'])

with (OUT/'TRACEABILITY_LINKS.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['FR ID','UC ID','Linked TC IDs','Number of Designed TCs','Case Study Approval Status'])
 for req in D['fr']:
  test_ids=[case.id for case in tests.values() if req['id'] in case.related_requirements]
  w.writerow([req['id'],req['uc'],'; '.join(test_ids),len(test_ids),req['status']])

print('Generated 12 use cases, 50 test cases and requirement-to-test traceability exports in',OUT)
