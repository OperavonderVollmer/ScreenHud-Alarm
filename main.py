from Alarm import Alarm
from OperaPowerRelay import opr
import os, shutil, tempfile

import datetime
if __name__ == '__main__':
    
    # alarm_list = []

    # for alarm in Alarm.test_cases:
    #     alarm_list.append(Alarm.Alarm(**alarm))

    # for alarm in alarm_list:
    #     time = alarm.calculate_time()
    #     print(f"{alarm.title} : {time} -> {(time - datetime.datetime.now()).total_seconds()} seconds")

    
    alarm_manager = Alarm.AlarmManager()
    # alarm_manager.load_alarms()
    # for alarm in alarm_manager.list_alarms():
    #     time = alarm.calculate_time()
    #     if not time:
    #         print(f"Alarm not started: {alarm.title}")
    #     else:
    #         print(f"{alarm.title} : {time} -> {(time - datetime.datetime.now()).total_seconds()} seconds")

    for alarm in Alarm.test_cases:
        alarm_manager.add_alarm(**alarm)

    alarm_manager.save_alarms()