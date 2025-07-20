from OperaPowerRelay import opr
from pydantic import BaseModel, model_validator
import datetime
import os
import shutil
import tempfile
import time
import threading
from dotenv import load_dotenv
import socket
import struct
import json
from enum import Enum, auto
from typing import Optional
import calendar


load_dotenv()   

HUD_HOST = str(os.getenv("HUD_HOST", "127.0.0.1"))
HUD_PORT = int(os.getenv("HUD_PORT", 56000))


compare_time = datetime.datetime(2025, 1, 5, 7, 0) # 5th of january 2025 at 7 AM
test_cases = [
    {   # Wake up for work. Create at January 5, 2025. Triggers every day at 8:00 AM
        "title": "Wake up for work",
        "subtitle": "Wake up",
        "description": "Make sure to brush teeth and have breakfast",
        "subdescription": "Do daily routine",
        "creation": datetime.date(2025, 1, 5),
        "trigger": datetime.time(8, 0),
        "reoccurence_type": "DAILY",
    },
    {   # Go grocery shopping. Create at January 5, 2025. Triggers every monday and friday at 6:00 PM
        "title": "Go grocery shopping",
        "subtitle": "Grocery",
        "description": "Check reserves for beer and bread",
        "creation": datetime.date(2025, 1, 5),
        "trigger": datetime.time(18, 0),
        "reoccurence_type": "WEEKLY",
        "weekdays": [1, 5],
    },
    {   # Monthsary with my girlfriend. Create at January 5, 2025. Triggers monthly on the 5th
        "title": "Monthsary with my girlfriend",
        "description": "Allocate at least 500€ for the monthsary",
        "creation": datetime.date(2025, 1, 5),
        "trigger": datetime.time(8, 0),
        "reoccurence_type": "PERIODIC",
        "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "day": 5
    },
    {   # Mother's birthday. Create at January 5, 2025. Triggers yearly on January 4th
        "title": "Mother's birthday",
        "description": "Make sure to buy her a gift",
        "creation": datetime.date(2025, 1, 5),
        "trigger": datetime.time(8, 0),
        "reoccurence_type": "PERIODIC",
        "months": [1],
        "day": 4
    },
    {   # Oil change. Create at January 5, 2025. Triggers quarterly on the 1st
        "title": "Change oil on the Ninja",
        "description": "Jim's autoshop. Fourth avenue, 123",
        "creation": datetime.date(2025, 1, 4),
        "trigger": datetime.time(8, 0),
        "reoccurence_type": "PERIODIC",
        "months": [1, 4, 8, 11],
        "day": 1
    },
    {
        "title": "Visit the dentist today",
        "description": "Make sure to brush teeth and have breakfast",
        "creation": datetime.date(2025, 1, 5),
        "trigger": datetime.time(12, 0),
        "reoccurence_type": "NONE",
    }
]

class ReoccurenceType(str, Enum):
    NONE = "NONE"
    DONE = "DONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    PERIODIC = "PERIODIC"

class Alarm(BaseModel):
    title: str
    subtitle: str = "No subtitle"
    description: str = "No description"
    subdescription: str = "No subdescription"
    creation: datetime.date
    trigger: datetime.time
    reoccurence_type: ReoccurenceType
    """ Weekdays | Uses ISO weekdays (1-7)
    1 = Monday
    2 = Tuesday
    3 = Wednesday
    4 = Thursday
    5 = Friday
    6 = Saturday
    7 = Sunday    
    """
    weekdays: Optional[list[int]] = None
    """ Months
    1 = January 
    2 = February 
    3 = March
    4 = April
    5 = May
    6 = June
    7 = July
    8 = August
    9 = September
    10 = October
    11 = November
    12 = December
    """
    months: Optional[list[int]] = None
    days: Optional[list[int]] = None               # 1-31
    year: Optional[int] = None              # NOTE: ONLY USED FOR ONE-OFF ALARMS
    ticking: bool = False
    autopopped: bool = False

    @model_validator(mode="after")
    def populate_one_offs(cls, instance):
        if instance.reoccurence_type == ReoccurenceType.NONE:
            now = datetime.datetime.now()
            changed = False
            if not instance.days:
                if now.time() > instance.trigger:
                    instance.days = [now.day + 1]
                else:
                    instance.days = [now.day]
                changed = True
            if not instance.months:
                instance.months = [now.month]
                changed = True
            if not instance.year:
                instance.year = now.year
                changed = True
            if changed:
                instance.autopopped = True
        return instance
    
    def model_post_init(self, __context):
        self._stop_event = threading.Event()

    @classmethod
    def from_json(cls, data: dict) -> "Alarm":
        # Parse date and time from string if necessary
        if isinstance(data.get("creation"), str):
            data["creation"] = datetime.date.fromisoformat(data["creation"])
        if isinstance(data.get("trigger"), str):
            data["trigger"] = datetime.time.fromisoformat(data["trigger"])
        if isinstance(data.get("reoccurence_type"), str):
            data["reoccurence_type"] = ReoccurenceType(data["reoccurence_type"])
        for field in ["days", "months", "weekdays"]:
            if isinstance(data.get(field), int):
                data[field] = [data[field]]
        return cls(**data)
    
    def to_json(self) -> dict:
        return {k: v for k, v in {
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "subdescription": self.subdescription,
            "creation": self.creation.isoformat(),
            "trigger": self.trigger.isoformat(),
            "reoccurence_type": self.reoccurence_type.value,
            "weekdays": self.weekdays,
            "months": self.months,
            "days": self.days,
            "year": self.year
        }.items() if v is not None}

    def calculate_time(self) -> datetime.datetime | str:
        now = datetime.datetime.now()
        trigger_target = datetime.datetime.combine(now.date(), self.trigger)

        def safe_datetime(year, month, day):
            last_day = calendar.monthrange(year, month)[1]
            valid_day = min(day, last_day)
            return datetime.datetime(year, month, valid_day, self.trigger.hour, self.trigger.minute)

        def find_week() -> datetime.datetime | str:
            if not self.weekdays:
                m = f"Alarm {self.title} does not have a valid weekday"
                print(m)
                return m

            candidate_days = []

            for wday in self.weekdays:
                days_ahead = (wday - now.isoweekday()) % 7
                candidate_date = now + datetime.timedelta(days=days_ahead)
                candidate_trigger = datetime.datetime.combine(candidate_date.date(), self.trigger)

                if candidate_trigger <= now:
                    candidate_trigger += datetime.timedelta(days=7)

                candidate_days.append(candidate_trigger)

            if candidate_days:
                return min(candidate_days)
            else:
                m = f"Alarm {self.title} could not find a valid upcoming weekday trigger."
                print(m)
                return m
        
        def find_periodic() -> datetime.datetime | str:
            if not self.months or (not self.days and not self.weekdays):
                month = f"Alarm {self.title} does not have a valid periodic date"
                print(month)
                return month

            candidate_days = []
            year = now.year     

            for offset in range(2):
                if self.days:
                    for month in self.months:                    
                        for day in self.days:
                            safe_date = safe_datetime(year, month, day)
                            if safe_date > now:
                                candidate_days.append(safe_date)

                if self.weekdays:
                    for month in self.months:
                        # Generates all of the days in the month along with the trigger dates, then adds candidates based on weekdays
                        days_in_month = calendar.monthrange(year, month)[1]
                        for day in range(1, days_in_month + 1):
                            dt_candidate = datetime.datetime(year, month, day, self.trigger.hour, self.trigger.minute)
                            if dt_candidate.weekday() + 1 in self.weekdays and dt_candidate > now:
                                candidate_days.append(dt_candidate)

                if candidate_days:
                    break

                year += 1


            if candidate_days:
                candidate_days = list(set(candidate_days))  # Remove duplicates
                return min(candidate_days)
            else:
                error_message = f"Alarm {self.title} could not find a valid upcoming periodic trigger."
                print(error_message)
                return error_message


        match self.reoccurence_type:
            case ReoccurenceType.DONE:
                return f"Alarm {self.title} is done"

            case ReoccurenceType.DAILY:
                return trigger_target if now < trigger_target else trigger_target + datetime.timedelta(days=1)

            case ReoccurenceType.WEEKLY:
                return find_week()
            
            case ReoccurenceType.PERIODIC:
                return find_periodic()

            case ReoccurenceType.NONE:
                if not self.year or not self.months or not self.days:
                    m = f"Alarm {self.title} does not have a valid one-off date"
                    print(m)
                    return m
                
                final = datetime.datetime(self.year, self.months[0], self.days[0], self.trigger.hour, self.trigger.minute)

                if final < now:
                    if self.autopopped:
                        f = final + datetime.timedelta(days=1)
                        final = safe_datetime(f.year, f.month, f.day)
                        return final
                    else:
                        self.reoccurence_type = ReoccurenceType.DONE
                        return f"Alarm {self.title} is done"

                return final
            
            case _:
                return f"Alarm {self.title} does not have a valid reoccurence type"
                            



    def start(self) -> str:
        self.stop()
        self._stop_event.clear()
        t = self.calculate_time()
        if isinstance(t, str):
            return t
        t_in_seconds = int((t - datetime.datetime.now()).total_seconds())
        threading.Thread(target=self._alarm_thread, args=(t_in_seconds,), daemon=True).start()
        return f"Alarm started: {self.title} | Ringing in {t_in_seconds} seconds"

    def snooze(self, snooze_hours: int = 0, snooze_minutes: int = 10, snooze_seconds: int = 0) -> str:
        t = (snooze_hours * 3600) + (snooze_minutes * 60) + (snooze_seconds)

        if t <= 0:
            opr.write_log(isFrom="ScreenHud-Alarm", path=(os.path.join(opr.get_special_folder_path("Documents"), "Opera Tools")), filename="screenhud_alarms.log", message=f"Alarm Snoozed: {self.title} | Invalid snooze time, using default of 10 minutes", level="INFO")
            t = 600
        
        self.stop()
        self._stop_event.clear()
        threading.Thread(target=self._alarm_thread, args=(t,), daemon=True).start()
        return f"Alarm Snoozed: {self.title} | Ringing in {snooze_minutes} minutes"

    def buzz(self) -> tuple[str, bool]:
        global HUD_HOST, HUD_PORT

        if self.reoccurence_type == ReoccurenceType.NONE:
            self.reoccurence_type = ReoccurenceType.DONE

        payload_json = json.dumps(self.to_json())
        payload_bytes = payload_json.encode("utf-8")
        payload_size = len(payload_bytes)

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((HUD_HOST, HUD_PORT))
                size_packed = struct.pack("!I", payload_size)
                sock.sendall(size_packed + payload_bytes)

            return (f"SUCCESS: Alarm notification sent to {HUD_HOST}:{HUD_PORT}", True)
            
        except ConnectionRefusedError:
            return (f"FAILED: Connection refused {HUD_HOST}:{HUD_PORT}", False)
        except socket.gaierror:
            return (f"FAILED: Address-related error connecting to server {HUD_HOST}:{HUD_PORT}", False)
        except Exception as e:
            return (f"FAILED: Something went wrong - {e}", False)

    def _alarm_thread(self, t: int) -> None:
        """
        Manages the countdown for the alarm in a separate thread and triggers the alarm.

        This function runs in a separate thread to handle the countdown of the alarm.
        It periodically checks if the alarm should be stopped prematurely. If the countdown
        completes without interruption, it triggers the alarm by calling the `buzz` method.

        Parameters
        ----------
        t : int
            The initial countdown time in seconds.

        Returns
        -------
        None
        """

        self.ticking = True
        opr.write_log(
            isFrom="ScreenHud-Alarm",
            path=os.path.join(opr.get_special_folder_path("Documents"), "Opera Tools"),
            filename="screenhud_alarms.log",
            message=f"Alarm Ticking: {self.title}",
            level="INFO"
        )

        MAX_WAIT = 24 * 24 * 60 * 60  # 2,073,600 seconds = ~24 days

        try:
            remaining = t
            print(f"\nAlarm Ticking: {self.title}\nRinging in: {self.calculate_time()}\nWaiting: {opr.seconds_to_time(remaining)}\n")
            while remaining > 0:
                wait_time = min(remaining, MAX_WAIT - 1)
                if self._stop_event.wait(wait_time): return  # Interrupted manually
                remaining -= wait_time

            self.buzz()

        finally:
            self.ticking = False  # Ensure cleanup


    def stop(self) -> str:
        if hasattr(self, "_stop_event"):
            opr.write_log(isFrom="ScreenHud-Alarm", path=(os.path.join(opr.get_special_folder_path("Documents"), "Opera Tools")), filename="screenhud_alarms.log", message=f"Alarm stopped: {self.title}", level="INFO")
            self._stop_event.set()
            return f"Alarm stopped: {self.title}"

        return f"Alarm not started: {self.title}"

class AlarmManager:
    def __init__(self, filepath=None):
        self._filepath = filepath or os.path.join(opr.get_special_folder_path("Documents"), "Opera Tools", "screenhud_alarms.json")
        self._alarm_list: list[Alarm] = []
        self.load_alarms()
        self.shutdown_event = threading.Event()

    def boot_auto_save(self) -> None:
        threading.Thread(target=self.auto_save, daemon=True).start()

    def auto_save(self) -> None:
        # Save alarms every hour
        while True:
            try:            
                if self.shutdown_event.wait(3600):
                    return  
                self.save_alarms()
            except Exception as e:
                opr.error_pretty(exc=e, name="ScreenHud-Alarm", message="Error saving alarm list")
                continue
            finally:
                self.save_alarms()

    def load_alarms(self) -> str:
        self._alarm_list.clear()
        alarm_json = opr.load_json(is_from="ScreenHud-Alarm", path=os.path.dirname(self._filepath), filename="screenhud_alarms.json")
        if not alarm_json:
            return f"Alarm list not found: {self._filepath}"
        for alarm in alarm_json["alarms"]:
            self._alarm_list.append(Alarm.from_json(alarm))

        return f"Alarm list loaded: {len(self._alarm_list)} alarms"

# TODO: Json parameter which forces using alarm's from json method

    def add_alarm(self, alarm: Alarm = None, **kwargs) -> Alarm | None: # type: ignore

        if not alarm:        
            try:
                alarm = (Alarm(**kwargs))
            except Exception as e:
                opr.error_pretty(exc=e, name="ScreenHud-Alarm", message="Error adding alarm")
                return None

        self._alarm_list.append(alarm)
        self.save_alarms()
        return alarm
    
    def start_all_alarms(self) -> list[str]:
        resp = []
        for alarm in self._alarm_list:
            resp.append(alarm.start())

        return resp
    
    def start_alarm(self, name: str) -> str:
        for alarm in self._alarm_list:
            if alarm.title == name:
                return alarm.start()

        return f"Alarm not found: {name}"

    def list_alarms(self) -> list[Alarm]:

            return self._alarm_list

    def save_alarms(self) -> str:
        alarm_json = {"alarms": [a.to_json() for a in self._alarm_list]}
        message = opr.save_json(is_from="ScreenHud-Alarm", path=os.path.dirname(self._filepath), dump=alarm_json, filename="screenhud_alarms.json", use_temp=True)  
        return message

    def clear_all_alarms(self) -> str:

        self._alarm_list.clear()

        m = f"Alarm list cleared. {len(self._alarm_list)} alarms remaining. Make sure to save the alarm list before exiting the application."
        print(m)
        return m
    
    def clear_alarm(self, name: str) -> str:
        for alarm in self._alarm_list:
            if alarm.title == name:
                self._alarm_list.remove(alarm)

        m = f"Alarm {name} cleared. {len(self._alarm_list)} alarms remaining. Make sure to save the alarm list before exiting the application."
        print(m)
        return m