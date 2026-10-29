"""Python representations of the 50 HOAS planned acceptance test cases.

Catalogue existence != execution. The prototype execution ledger is separate.
Run: python -m src.test_cases TC-015
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json,sys
from .use_cases import DATA_PATH,load_catalog

@dataclass(frozen=True)
class TestCase:
    id: str
    use_case_id: str
    name: str
    kind: str
    requirement: str
    related_requirements: tuple[str,...]
    preconditions: str
    steps: str
    input_data: str
    expected_result: str
    documented_status: str

    @classmethod
    def from_row(cls,row:dict[str,Any]):
        return cls(row['id'],row['uc'],row['name'],row['kind'],row['requirement'],tuple(row['related']),row['precondition'],row['steps'],row['input'],row['expected'],row['status'])

    def as_markdown(self):
        return ('### '+self.id+' - '+self.name+'\n'
                +f'- Use case: {self.use_case_id}\n- Requirement: {self.requirement}\n- Category: {self.kind}\n'
                +f'- Preconditions: {self.preconditions}\n- Steps: {self.steps}\n- Input: {self.input_data}\n'
                +f'- Expected result: {self.expected_result}\n- Acceptance status: Not run on a hospital system\n')

def load_catalog():
    data=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    return {row['id']:TestCase.from_row(row) for row in data['tests']}

def validate_catalog():
    data=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    requirements={r['id'] for r in data['fr']}|{r['id'] for r in data['nfr']}
    ucs=set(load_use_cases())
    rows=data['tests'];ids=[row['id'] for row in rows]
    assert len(ids)==len(set(ids)), 'Duplicate TC identifier'
    assert len(ids)==50, f'Expected 50 catalog test cases, found {len(ids)}'
    for row in rows:
        t=TestCase.from_row(row)
        assert t.use_case_id in ucs, f'Unknown use case in {t.id}'
        assert t.requirement in requirements, f'Unknown requirement in {t.id}'
        assert all(r in requirements for r in t.related_requirements), f'Unknown linked requirement in {t.id}'
        assert t.requirement in t.related_requirements, f'Primary link is absent in {t.id}'
        assert all([t.name,t.expected_result,t.steps,t.preconditions]), f'Incomplete fields in {t.id}'
    return {'test_cases':len(rows),'links_valid':True}

def load_use_cases():return load_uc_catalog()
from .use_cases import load_catalog as load_uc_catalog

if __name__=='__main__':
    data=load_catalog()
    if len(sys.argv)>1:
        selected=sys.argv[1]
        if selected not in data: raise SystemExit(f'Unknown test case: {selected}')
        print(data[selected].as_markdown())
    else:
        print('\n'.join(tc.as_markdown() for tc in data.values()))
