"""50 uniquely identified catalogue-aligned prototype acceptance tests.

Each test corresponds to a TC-### entry in data/hoas_dataset.json.
They exercise synthetic in-memory model operations, not a real hospital system.
"""
from __future__ import annotations
import unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from src.hoas import HOASPrototype, Slot, RuleError, AccessDenied

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)

class HOASAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.model=HOASPrototype(clock=lambda:NOW)
        self.model.add_slot('admin',Slot('S1','Dr An','Gastroenterology',NOW+timedelta(days=3),1))
        self.model.add_slot('admin',Slot('S2','Dr Binh','Internal Medicine',NOW+timedelta(days=4),2))

    def patient(self,phone='0912345678'):
        self.model.register_patient('Sample Patient',phone,'2001-06-10','SamplePass123')
        return phone

    def booking(self,patient='patient1',slot='S1'):
        return self.model.book(patient,slot)

    def extra_slot(self,slot_id='S3',hours=72,doctor='Dr C',specialty='Dermatology',capacity=1):
        self.model.add_slot('admin',Slot(slot_id,doctor,specialty,NOW+timedelta(hours=hours),capacity))

    # UC-01: Register and Sign In
    def test_TC_001_valid_registration(self):
        p=self.patient();self.assertIn(p,self.model.patients)
    def test_TC_002_missing_date_of_birth(self):
        with self.assertRaisesRegex(RuleError,'required'):self.model.register_patient('A','0912345678','','Password123')
    def test_TC_003_duplicate_phone_number(self):
        p=self.patient()
        with self.assertRaisesRegex(RuleError,'duplicate'):self.model.register_patient('Another',p,'1999-01-01','Password123')
    def test_TC_004_valid_sign_in(self):
        p=self.patient();login=self.model.login_patient(p,'SamplePass123')
        self.assertEqual(login['role'],'Patient');self.assertTrue(login['session_id'])
    def test_TC_005_incorrect_password(self):
        p=self.patient()
        with self.assertRaises(AccessDenied):self.model.login_patient(p,'WrongPassword')

    # UC-02: Manage Patient Profile
    def test_TC_006_view_own_profile(self):
        p=self.patient();self.assertEqual(self.model.patient_profile(p,p)['phone'],p)
        with self.assertRaises(AccessDenied):self.model.patient_profile('another',p)
    def test_TC_007_update_address(self):
        p=self.patient();self.model.update_patient_profile(p,p,address='123 Example Street')
        self.assertEqual(self.model.patient_profile(p,p)['address'],'123 Example Street')
    def test_TC_008_invalid_contact_information(self):
        p=self.patient();old=self.model.patient_profile(p,p)
        with self.assertRaises(RuleError):self.model.update_patient_profile(p,p,phone_number='bad')
        self.assertEqual(self.model.patient_profile(p,p),old)

    # UC-03: Search Doctors and Available Slots
    def test_TC_009_search_gastroenterology(self):
        self.assertEqual(self.model.find_doctors('Gastroenterology'),['Dr An'])
    def test_TC_010_available_slot_has_capacity(self):
        s=self.model.visible_slots('Gastroenterology')[0]
        self.assertEqual(s.capacity-s.booked,1)
    def test_TC_011_fully_booked_slot(self):
        self.booking();self.assertNotIn('S1',[s.id for s in self.model.visible_slots()])
    def test_TC_012_date_with_no_appointments(self):
        dates=self.model.search_available_dates('Gastroenterology')
        self.assertIn((NOW+timedelta(days=3)).date().isoformat(),dates)
        self.assertNotIn((NOW+timedelta(days=8)).date().isoformat(),dates)

    # UC-04: Book an Appointment
    def test_TC_013_book_available_slot(self):
        a=self.booking();self.assertEqual(a.status,'Confirmed');self.assertTrue(a.id.startswith('HOAS-'))
    def test_TC_014_repeated_appointment_id(self):
        a=self.booking(slot='S2');b=self.booking(patient='patient2',slot='S2')
        self.assertNotEqual(a.id,b.id)
    def test_TC_015_two_patients_compete_for_one_place(self):
        self.booking()
        with self.assertRaises(RuleError):self.booking(patient='patient2')
        self.assertEqual(self.model.slots['S1'].booked,1)
    def test_TC_016_one_hundred_threads_compete(self):
        def submit(n):
            try:self.booking(f'patient{n}');return True
            except RuleError:return False
        with ThreadPoolExecutor(max_workers=20) as pool:results=list(pool.map(submit,range(100)))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.model.slots['S1'].booked,1)
    def test_TC_017_doctor_becomes_unavailable(self):
        self.model.suspend_slot('admin','S1')
        with self.assertRaises(RuleError):self.booking()
    def test_TC_018_already_full_slot(self):
        self.booking()
        with self.assertRaises(RuleError):self.booking('patient2')
        self.assertEqual(self.model.slots['S1'].booked,1)

    # UC-05: View My Appointments
    def test_TC_019_list_own_appointments(self):
        self.booking('patient1')
        self.assertEqual(self.model.owned('patient2'),[])
        self.assertEqual(len(self.model.owned('patient1')),1)
    def test_TC_020_read_another_patients_appointment(self):
        a=self.booking('patient1')
        with self.assertRaises(AccessDenied):self.model.appointment_detail('patient2',a.id)
    def test_TC_021_view_booking_details(self):
        a=self.booking();detail=self.model.appointment_summary('patient1',a.id)
        self.assertEqual(detail['code'],a.id)
        for field in ('doctor','specialty','start','status'):self.assertTrue(detail[field])

    # UC-06: Cancel an Appointment
    def test_TC_022_cancel_more_than_24_hours_early(self):
        a=self.booking();self.model.cancel('patient1',a.id)
        self.assertEqual(a.status,'Cancelled');self.assertEqual(self.model.slots['S1'].booked,0)
    def test_TC_023_cancel_at_exact_12_hour_boundary(self):
        self.extra_slot(hours=12);a=self.booking(slot='S3')
        self.model.cancel('patient1',a.id);self.assertEqual(a.status,'Cancelled')
    def test_TC_024_cancel_only_three_hours_early(self):
        self.extra_slot(hours=3);a=self.booking(slot='S3')
        with self.assertRaises(RuleError):self.model.cancel('patient1',a.id)
        self.assertEqual(self.model.slots['S3'].booked,1)
    def test_TC_025_unauthorized_cancellation(self):
        a=self.booking('patient1')
        with self.assertRaises(AccessDenied):self.model.cancel('patient2',a.id)
    def test_TC_026_repeat_cancellation(self):
        a=self.booking();self.model.cancel('patient1',a.id)
        with self.assertRaises(RuleError):self.model.cancel('patient1',a.id)
        self.assertEqual(self.model.slots['S1'].booked,0)

    # UC-07: Reschedule an Appointment
    def test_TC_027_reschedule_with_at_least_12_hours(self):
        a=self.booking();self.model.reschedule('patient1',a.id,'S2')
        self.assertEqual(a.slot_id,'S2');self.assertEqual(self.model.slots['S1'].booked,0)
    def test_TC_028_reschedule_with_only_two_hours(self):
        self.extra_slot(hours=2);a=self.booking(slot='S3')
        with self.assertRaises(RuleError):self.model.reschedule('patient1',a.id,'S2')
        self.assertEqual(a.slot_id,'S3')
    def test_TC_029_reschedule_to_full_slot(self):
        a=self.booking();self.booking('p2','S2');self.booking('p3','S2')
        with self.assertRaises(RuleError):self.model.reschedule('patient1',a.id,'S2')
        self.assertEqual(a.slot_id,'S1')
    def test_TC_030_mid_transaction_failure(self):
        a=self.booking()
        with self.assertRaises(RuntimeError):self.model.reschedule('patient1',a.id,'S2',inject_failure=True)
        self.assertEqual(a.slot_id,'S1')
        self.assertEqual((self.model.slots['S1'].booked,self.model.slots['S2'].booked),(1,0))

    # UC-08: Patient Check-in
    def test_TC_031_check_in_confirmed_appointment(self):
        a=self.booking();self.model.check_in('reception',a.id)
        self.assertEqual(a.status,'Checked-in')
    def test_TC_032_check_in_cancelled_appointment(self):
        a=self.booking();self.model.cancel('patient1',a.id)
        with self.assertRaises(RuleError):self.model.check_in('reception',a.id)
    def test_TC_033_repeated_check_in(self):
        a=self.booking();self.model.check_in('reception',a.id)
        with self.assertRaises(RuleError):self.model.check_in('reception',a.id)
    def test_TC_034_unknown_appointment_id(self):
        with self.assertRaisesRegex(RuleError,'appointment not found'):
            self.model.appointment_by_code('reception','HOAS-UNKNOWN')

    # UC-09: Manage Consultation Progress
    def test_TC_035_doctor_views_assigned_list(self):
        self.booking();self.booking('p2','S2')
        visits=self.model.doctor_queue('Dr An','Dr An',(NOW+timedelta(days=3)).date())
        self.assertEqual(len(visits),1)
    def test_TC_036_doctor_accesses_other_list(self):
        with self.assertRaises(AccessDenied):
            self.model.doctor_queue('Dr Binh','Dr An',(NOW+timedelta(days=3)).date())
    def test_TC_037_begin_consultation_in_valid_status(self):
        a=self.booking();self.model.check_in('reception',a.id)
        self.model.doctor_update('Dr An',a.id,'In Progress')
        self.assertEqual(a.status,'In Progress')
    def test_TC_038_begin_before_checkin(self):
        a=self.booking()
        with self.assertRaises(RuleError):self.model.doctor_update('Dr An',a.id,'In Progress')
    def test_TC_039_complete_consultation(self):
        a=self.booking();self.model.check_in('reception',a.id)
        self.model.doctor_update('Dr An',a.id,'In Progress')
        self.model.doctor_update('Dr An',a.id,'Completed');self.assertEqual(a.status,'Completed')

    # UC-10: Manage Physician Schedules
    def test_TC_040_create_eligible_slot(self):
        self.extra_slot();self.assertIn('S3',self.model.slots)
    def test_TC_041_create_overlapping_doctor_slot(self):
        with self.assertRaises(RuleError):
            self.model.add_slot('admin',Slot('X','Dr An','Gastroenterology',NOW+timedelta(days=3),1))
    def test_TC_042_unexpected_doctor_absence(self):
        a=self.booking();self.model.suspend_slot('admin','S1')
        self.assertEqual(a.status,'Needs Rescheduling')
    def test_TC_043_audit_physician_schedule_update(self):
        self.model.suspend_slot('admin','S1')
        last=[a for a in self.model.audit if a['action']=='schedule_change'][-1]
        self.assertIn('actor',last);self.assertIn('at',last)
        self.assertIn('before',last['details']);self.assertIn('after',last['details'])

    # UC-11: Send Appointment Notifications
    def test_TC_044_booking_produces_outbox_event(self):
        self.booking();events=self.model.outbox
        self.assertEqual(len(events),1);self.assertTrue(events[0]['event_id'])
    def test_TC_045_cancellation_produces_outbox_event(self):
        a=self.booking();self.model.cancel('patient1',a.id)
        self.assertEqual(self.model.outbox[-1]['kind'],'BookingCancelled')
    def test_TC_046_provider_delivery_failure(self):
        a=self.booking();self.assertFalse(self.model.send_notification(0,False))
        self.assertEqual(a.status,'Confirmed')
    def test_TC_047_provider_retries_event(self):
        self.booking();ident=self.model.outbox[0]['event_id']
        self.model.send_notification(0,False);self.model.send_notification(0,True)
        self.assertEqual(len(self.model.outbox),1)
        self.assertEqual(self.model.outbox[0]['event_id'],ident)

    # UC-12: Generate Reports and Review Audit Logs
    def test_TC_048_correct_appointment_status_summary(self):
        self.booking();self.booking('p2','S2')
        a=self.model.owned('patient1')[0];self.model.cancel('patient1',a.id)
        totals=self.model.admin_summary('admin')
        self.assertEqual(totals['Confirmed'],1);self.assertEqual(totals['Cancelled'],1)
    def test_TC_049_audit_fields_present(self):
        self.booking();record=[r for r in self.model.audit if r['action']=='book'][0]
        for field in ('actor','action','at'):self.assertIn(field,record)
    def test_TC_050_patient_requests_administrative_report(self):
        with self.assertRaises(AccessDenied):self.model.admin_summary('patient1')

if __name__ == '__main__': unittest.main(verbosity=2)
