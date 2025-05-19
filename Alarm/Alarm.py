from OperaPowerRelay import opr
from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime
import os
import shutil
import tempfile
    

class Alarm(BaseModel):
    """
    A class representing an alarm.

    Parameters
    ----------
    title : str
        The title of the alarm.
    subtitle : str, optional
        The subtitle of the alarm. Defaults to the value of `title`.
    description : str
        The description of the alarm.
    short_description : str, optional
        The short description of the alarm. Defaults to the value of `description`.
    create_date : datetime
        The datetime the alarm was created.
    end_date : datetime
        The datetime the alarm ends.

    Returns
    -------
    Alarm
        A new Alarm instance.

    Notes
    -----
    The `end_date` is validated to be after `create_date`.

    """
    
    title: str
    subtitle: str = ""
    description: str
    short_description: str = ""
    create_date: datetime
    end_date: datetime

    @field_validator("end_date", mode="after")
    def end_date_after_create_date(cls, v, info):
        create_date = info.data.get("create_date")
        if create_date and v < create_date:
            raise ValueError("End date must be after create date")
        return v

    @model_validator(mode="after")
    def fill_missing_fields(cls, model):
        if not model.subtitle:
            model.subtitle = model.title
        if not model.short_description:
            model.short_description = model.description
        return model

    def to_json(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_json(cls, data: dict) -> "Alarm":
        return cls(**data)
    
    def start(self):
        delta = opr.get_seconds()
        pass

    # TODO: snooze time is in minutes
    def snooze(self, snooze_time: int = 5):
        pass



class AlarmManager:
    def __init__(self, filepath=None):
        self._filepath = filepath or opr.get_special_folder_path("Documents")
        self._alarm_list: list[Alarm] = []
        self.load_alarms()

    def load_alarms(self) -> None:
        self._alarm_list.clear()
        alarm_json = opr.load_json(is_from="ScreenHud-Alarm", path=os.path.dirname(self._filepath), filename="screenhud_alarms.json")
        
        for _ in alarm_json.setdefault("alarms", []):
            self._alarm_list.append(Alarm.from_json(_))

    def add_alarm(self, alarm: Alarm = None, **kwargs) -> Alarm | None: # type: ignore

        if not alarm:        
            try:
                alarm = (Alarm(**kwargs))
            except Exception as e:
                opr.error_pretty(exc=e, name="ScreenHud-Alarm", message="Error adding alarm")
                return None

        self._alarm_list.append(alarm)
        return alarm
    
    def start_alarms(self) -> None:
        for _ in self._alarm_list:
            _.start()


    def save_alarms(self) -> None:

        alarm_json = {"alarms": [a.to_json() for a in self._alarm_list]}
        dir_path = os.path.dirname(self._filepath)
        fd, temp_path = tempfile.mkstemp(dir=dir_path)
        os.close(fd)

        opr.save_json(is_from="ScreenHud-Alarm", path=dir_path, filename=os.path.basename(temp_path), dump=alarm_json)
        shutil.move(temp_path, os.path.join(dir_path, "screenhud_alarms.json"))

    def clear_alarms(self) -> None:

        self._alarm_list.clear()

        print("Alarm list cleared. Make sure to save changes")