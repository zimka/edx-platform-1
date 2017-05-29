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
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)

    @classmethod
    def actions_for_course(cls, course_id):
        return cls.objects.filter(course_id=course_id)



