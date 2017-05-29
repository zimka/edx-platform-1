# -*- coding: utf-8 -*-
import json
import logging

from track.backends import BaseBackend
from .models import InstructorResetStudentAttempts


class CustomTrackerBackend(BaseBackend):
    """
    Это бэкенд к старой системе трекинга OpenEdx в виде djangoapp, ее можно найти в common/djagnoapps/track.
    С ее помощью пишется tracking.log. Из таких логов доступны фактически только url, по которым делались обращения
    """

    def send(self, event):
        """
        Записывает действия инструктора связанные с изменением ответов студента
        """
        if "reset" in event['event_type']:
            instructor_username = event['username']
            course_id = event['context']['course_id']
            event_dict = json.loads(event['event'])['POST']
            action = "delete" if json.loads(event_dict['delete_module'][0]) else "reset"
            student_username = event_dict["unique_student_identifier"][0]
            block_id = event_dict['problem_to_reset'][0]
            try:
                InstructorResetStudentAttempts.objects.create(
                    instructor_username=instructor_username,
                    student_username=student_username,
                    block_id=block_id,
                    course_id=course_id,
                    action=action,
                )
            except Exception as e:
                logging.error("Error during instructor_reset_track: '{}'".format(str(e)))