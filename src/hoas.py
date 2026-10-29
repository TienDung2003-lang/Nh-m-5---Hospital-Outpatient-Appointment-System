"""Small executable domain model for requirements verification, NOT a hospital product."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from threading import RLock
from uuid import uuid4

class RuleError(ValueError): pass
class AccessDenied(PermissionError): pass

@dataclass
class Slot:
    id: str
    doctor: str
    specialty: str
    start: datetime
    capacity: int
    booked: int = 0
    suspended: bool = False

@dataclass
class Appointment:
    id: str
    patient: str
    slot_id: str
    status: str = 'Confirmed'

class HOASModel:
    def __init__(self, clock=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.slots = {}
        self.appointments = {}
        self.audit = []
        self.outbox = []
        self._lock = RLock()

    def log(self,actor,action,details):
        self.audit.append(dict(actor=actor,action=action,at=self.clock().isoformat(),details=details))

    def add_slot(self,actor,slot):
        if actor!='admin': raise AccessDenied('admin only')
        if slot.capacity<1 or slot.start<=self.clock():raise RuleError('invalid slot')
        with self._lock:
            if slot.id in self.slots: raise RuleError('duplicate ID')
            for existing in self.slots.values():
                if not existing.suspended and existing.doctor==slot.doctor and existing.start==slot.start:
                    raise RuleError('doctor schedule conflict')
            self.slots[slot.id]=slot
            self.log(actor,'create_slot',slot.id)

    def visible_slots(self,specialty=None):
        return [s for s in self.slots.values() if s.start>self.clock() and not s.suspended and s.booked<s.capacity and (specialty is None or s.specialty==specialty)]

    def _event(self,appointment,kind):
        self.outbox.append(dict(event_id=str(uuid4()),appointment_id=appointment.id,kind=kind,state='Queued'))

    def book(self,patient,slot_id):
        if not patient: raise RuleError('patient required')
        with self._lock:
            if slot_id not in self.slots: raise RuleError('unknown slot')
            slot=self.slots[slot_id]
            if slot.suspended or slot.start<=self.clock() or slot.booked>=slot.capacity: raise RuleError('slot unavailable')
            a=Appointment('HOAS-'+uuid4().hex[:12].upper(),patient,slot_id)
            slot.booked+=1
            self.appointments[a.id]=a
            self.log(patient,'book',a.id)
            self._event(a,'BookingConfirmed')
            return a

    def owned(self,patient):
        return [a for a in self.appointments.values() if a.patient==patient]

    def appointment_detail(self,actor,appointment_id):
        a=self.appointments[appointment_id]
        if actor not in [a.patient,'reception','admin',self.slots[a.slot_id].doctor]: raise AccessDenied('owner/role only')
        return a

    def _owner_eligible(self,patient,app_id,cutoff_hours=12):
        a=self.appointment_detail(patient,app_id)
        if a.patient!=patient: raise AccessDenied('not owner')
        if a.status!='Confirmed': raise RuleError('not confirmed')
        if self.slots[a.slot_id].start-self.clock()<timedelta(hours=cutoff_hours): raise RuleError('cutoff')
        return a

    def cancel(self,patient,app_id):
        with self._lock:
            a=self._owner_eligible(patient,app_id)
            slot=self.slots[a.slot_id]
            a.status='Cancelled';slot.booked-=1
            self.log(patient,'cancel',app_id);self._event(a,'BookingCancelled')

    def reschedule(self,patient,app_id,new_id,inject_failure=False):
        with self._lock:
            a=self._owner_eligible(patient,app_id)
            if new_id not in self.slots: raise RuleError('unknown new slot')
            old=self.slots[a.slot_id];new=self.slots[new_id]
            if new_id==a.slot_id:return
            if new.suspended or new.start<=self.clock() or new.booked>=new.capacity: raise RuleError('new slot unavailable')
            # validate everything, then perform one protected transaction; any injected failure rolls back
            snapshot=(a.slot_id,old.booked,new.booked)
            try:
                old.booked-=1;new.booked+=1;a.slot_id=new_id
                if inject_failure:raise RuntimeError('injected database transaction failure')
            except Exception:
                a.slot_id,old.booked,new.booked=snapshot
                raise
            self.log(patient,'reschedule',app_id);self._event(a,'BookingRescheduled')

    def check_in(self,role,app_id,identity_verified=True):
        if role!='reception':raise AccessDenied('reception only')
        if not identity_verified:raise RuleError('identity mismatch')
        with self._lock:
            a=self.appointments[app_id]
            if a.status!='Confirmed':raise RuleError('not confirmed')
            a.status='Checked-in';self.log(role,'checkin',app_id)

    def doctor_update(self,doctor,app_id,next_status):
        with self._lock:
            a=self.appointments[app_id]
            if self.slots[a.slot_id].doctor!=doctor:raise AccessDenied('doctor mismatch')
            permitted={'Checked-in':'In Progress','In Progress':'Completed'}
            if permitted.get(a.status)!=next_status:raise RuleError('invalid state transition')
            a.status=next_status;self.log(doctor,'doctor_update',app_id)

    def doctor_daily_queue(self,doctor,on_date):
        return [a for a in self.appointments.values() if self.slots[a.slot_id].doctor==doctor and self.slots[a.slot_id].start.date()==on_date]

    def suspend_slot(self,role,slot_id):
        if role!='admin':raise AccessDenied('admin only')
        with self._lock:
            s=self.slots[slot_id];s.suspended=True
            for a in self.appointments.values():
                if a.slot_id==slot_id and a.status=='Confirmed':a.status='Needs Rescheduling'
            self.log(role,'suspend_slot',slot_id)

    def admin_summary(self,role):
        if role!='admin':raise AccessDenied('admin only')
        statuses=('Confirmed','Checked-in','In Progress','Completed','Cancelled','No-show','Needs Rescheduling')
        return {status:sum(a.status==status for a in self.appointments.values()) for status in statuses}

    def audit_view(self,role):
        if role!='admin':raise AccessDenied('admin only')
        return list(self.audit)

    def send_notification(self,index,provider_available=True):
        event=self.outbox[index]
        if not provider_available:
            event['state']='RetryQueued';return False
        event['state']='Sent';return True


class HOASPrototype(HOASModel):
    """Additional in-memory student prototype operations for catalogue test cases.

    Uses synthetic records; real identity verification, integrations and persistence
    are intentionally outside this teaching model.
    """
    def __init__(self, clock=None):
        super().__init__(clock)
        self.patients = {}
        self._credentials = {}
        self._sessions = {}

    def register_patient(self, name, phone, date_of_birth, password, address=''):
        import hashlib, os
        if not all(isinstance(v, str) and v.strip() for v in [name,phone,date_of_birth,password]):
            raise RuleError('required registration field missing')
        if not phone.isdigit() or len(phone) < 9 or len(password) < 8:
            raise RuleError('invalid contact or password')
        if phone in self.patients:
            raise RuleError('duplicate phone number')
        salt=os.urandom(16)
        digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        self.patients[phone]=dict(name=name,phone=phone,date_of_birth=date_of_birth,address=address)
        self._credentials[phone]=(salt,digest)
        self.log(phone,'register',phone)
        return phone

    def login_patient(self, phone, password):
        import hashlib, hmac
        if phone not in self._credentials: raise AccessDenied('invalid credentials')
        salt,actual=self._credentials[phone]
        provided=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,100000)
        if not hmac.compare_digest(provided,actual):
            raise AccessDenied('invalid credentials')
        token='SESSION-'+uuid4().hex
        self._sessions[token]=(phone,'patient')
        return {'session_id':token,'actor':phone,'role':'Patient'}

    def patient_profile(self, actor, phone):
        if actor != phone:raise AccessDenied('patient profile is private')
        return dict(self.patients[phone])

    def update_patient_profile(self, actor, phone, *, address=None, phone_number=None):
        if actor != phone:raise AccessDenied('not the patient')
        if phone_number is not None and (not phone_number.isdigit() or len(phone_number)<9 or (phone_number != phone and phone_number in self.patients)):
            raise RuleError('invalid or duplicate phone number')
        if address is not None and (not isinstance(address,str) or not address.strip()):
            raise RuleError('invalid address')
        with self._lock:
            if address is not None:self.patients[phone]['address']=address
            if phone_number and phone_number!=phone:
                profile=self.patients.pop(phone)
                profile['phone']=phone_number
                self.patients[phone_number]=profile
                self._credentials[phone_number]=self._credentials.pop(phone)
            self.log(actor,'update_profile',phone)

    def find_doctors(self, specialty):
        return sorted({slot.doctor for slot in self.visible_slots(specialty)})

    def search_available_dates(self, specialty):
        return sorted({slot.start.date().isoformat() for slot in self.visible_slots(specialty)})

    def appointment_summary(self, actor, appointment_id):
        a=self.appointment_detail(actor,appointment_id)
        s=self.slots[a.slot_id]
        return dict(code=a.id,doctor=s.doctor,specialty=s.specialty,start=s.start.isoformat(),status=a.status,patient=a.patient)

    def appointment_by_code(self, actor, appointment_id):
        if appointment_id not in self.appointments:raise RuleError('appointment not found')
        return self.appointment_summary(actor,appointment_id)

    def doctor_queue(self, actor, doctor, on_date):
        if actor!=doctor:raise AccessDenied('not assigned doctor')
        return self.doctor_daily_queue(doctor,on_date)

    def suspend_slot(self, role, slot_id):
        before={'suspended':self.slots[slot_id].suspended,'booked':self.slots[slot_id].booked}
        super().suspend_slot(role,slot_id)
        after={'suspended':self.slots[slot_id].suspended,'booked':self.slots[slot_id].booked}
        self.log(role,'schedule_change',{'slot':slot_id,'before':before,'after':after})
