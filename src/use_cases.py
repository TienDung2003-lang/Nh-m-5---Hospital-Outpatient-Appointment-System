"""Executable-friendly source of the 12 approved-draft HOAS use-case specifications.

These are records and validation routines, not a graphical user interface.
Run: python -m src.use_cases UC-04
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json,sys

DATA_PATH=Path(__file__).resolve().parents[1]/'data'/'hoas_dataset.json'

@dataclass(frozen=True)
class UseCase:
    id: str
    title: str
    actor: str
    secondary: str
    summary: str
    preconditions: str
    success_postconditions: str
    failure_postconditions: str
    main_steps: tuple[str,...]
    extensions: tuple[dict[str,str],...]
    nfr_links: tuple[str,...]
    priority: str

    @classmethod
    def from_row(cls,row:dict[str,Any]):
        return cls(row['id'],row['title'],row['actor'],row['secondary'],row['summary'],row['pre'],row['success'],row['failure'],tuple(row['steps']),tuple(row['extensions']),tuple(row['nfr']),row['priority'])

    def as_markdown(self):
        output=[f'## {self.id} - {self.title}',f'- Primary actor: {self.actor}',f'- Secondary actor: {self.secondary}',f'- Priority: {self.priority}',f'- Preconditions: {self.preconditions}',f'- Success postconditions: {self.success_postconditions}',f'- Failure postconditions: {self.failure_postconditions}','', '### Main Success Scenario']
        output.extend(f'{i}. {step}' for i,step in enumerate(self.main_steps,1))
        output.extend(['','### Extensions'])
        output.extend(f'- {e["ref"]}: If {e["condition"]}, {e["response"]}.' for e in self.extensions)
        output.extend(['','### Special Requirements',f'- Related NFRs: {", ".join(self.nfr_links) if self.nfr_links else "None identified"}',''])
        return '\n'.join(output)

def load_catalog():
    obj=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    return {u['id']:UseCase.from_row(u) for u in obj['ucs']}

def validate_catalog():
    data=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    ids=set();nfr={r['id'] for r in data['nfr']};actors={a['name'] for a in data['actors']}
    for case in load_catalog().values():
        assert case.id not in ids, f'Duplicate use case: {case.id}'
        ids.add(case.id)
        assert case.id.startswith('UC-') and case.title and case.actor and len(case.main_steps)>=3
        assert case.actor in actors, f'Unknown actor in {case.id}: {case.actor}'
        assert case.preconditions and case.success_postconditions and case.failure_postconditions
        assert case.priority in ('Must','Should','Could','Wont')
        assert all(ref in nfr for ref in case.nfr_links),f'Unrecognized NFR for {case.id}'
        for e in case.extensions: assert e['ref'] and e['condition'] and e['response']
    return {'use_cases':len(ids),'valid_nfr_links':True}

if __name__=='__main__':
    data=load_catalog()
    if len(sys.argv)>1:
        selected=sys.argv[1]
        if selected not in data:raise SystemExit(f'Unknown use case: {selected}')
        print(data[selected].as_markdown())
    else:
        print('\n\n'.join(case.as_markdown() for case in data.values()))
