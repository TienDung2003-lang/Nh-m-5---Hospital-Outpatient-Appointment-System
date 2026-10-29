"""Validates the entire source-of-truth dataset, not an application deployment."""
import unittest,json
from src.use_cases import load_catalog as load_ucs,validate_catalog as validate_ucs,DATA_PATH
from src.test_cases import load_catalog as load_tcs,validate_catalog as validate_tcs

class SpecificationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    def test_01_twelve_use_cases_have_valid_fields(self):
        self.assertEqual(validate_ucs()['use_cases'],12)
    def test_02_fifty_test_cases_have_valid_references(self):
        self.assertEqual(validate_tcs()['test_cases'],50)
    def test_03_every_functional_requirement_links_a_use_case(self):
        ucs=set(load_ucs());self.assertEqual(len(self.data['fr']),30)
        for r in self.data['fr']:
            with self.subTest(req=r['id']): self.assertIn(r['uc'],ucs)
    def test_04_each_use_case_has_test_cases(self):
        counts={uc:0 for uc in load_ucs()}
        for case in load_tcs().values():counts[case.use_case_id]+=1
        for uc,num in counts.items():
            with self.subTest(uc=uc):self.assertGreaterEqual(num,1)
    def test_05_all_business_rules_are_unique(self):
        rules=[r['id'] for r in self.data['br']]
        self.assertEqual(len(rules),len(set(rules)))
    def test_06_scenario_links_are_real(self):
        for row in self.data['scenarios']:
            for ref in [x.strip() for x in row['usecases'].split(';')]:
                with self.subTest(scenario=row['id'],uc=ref):self.assertIn(ref,load_ucs())
    def test_07_member_assignment_is_four_unique_people(self):
        members=self.data['members']
        self.assertEqual(len(members),4)
        self.assertEqual(len({m['student_id'] for m in members}),4)
