import json
import logging

from django.contrib.auth.models import User
from django.db import models, transaction
from util.db import outer_atomic
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from xmodule_django.models import CourseKeyField

log = logging.getLogger(__name__)


class InstructorResetStudentAttempts(models.Model):
    """
    This model contains records about instructor's actions on students:
    attempt deletion, attempt resetting
    """

    ACTION_CHOICES = (
        ("delete", "delete"),
        ("reset", "reset"),
    )
    instructor_username = models.CharField(max_length=50)
    student_username = models.CharField(max_length=50)
    block_id = models.CharField(max_length=300)
    course_id = models.CharField(max_length=150)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    removed_answer = models.TextField(default="")

    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    @classmethod
    def actions_for_course(cls, course_id):
        return cls.objects.filter(course_id=course_id)

    @classmethod
    def create(cls, instructor_username, student_username, course_id, block_id, action):
        answer = ""
        if action == "delete":
            answer = _get_current_user_answer(student_username, block_id)
        cls.objects.create(
            instructor_username=instructor_username,
            student_username=student_username,
            course_id=course_id,
            block_id=block_id,
            removed_answer=answer,
            action=action
        )

    @classmethod
    def approve(cls, response_content):
        if not "problem_to_reset" in response_content:
            return
        response_dict = json.loads(response_content)
        cls.objects.filter(student_username=response_dict["student"],
            block_id=response_dict["problem_to_reset"]
        )


def _get_current_user_answer(username_or_email, block_id):
    try:
        if "@" in username_or_email:
            user = User.objects.get(email=username_or_email)
        else:
            user = User.objects.get(username=username_or_email)
    except User.DoesNotExist:
        return "User not found for username {}".format(username_or_email)
    return "dummy"