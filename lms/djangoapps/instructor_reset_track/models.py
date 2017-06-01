from datetime import datetime
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone

from opaque_keys.edx.keys import UsageKey
from xmodule.modulestore.django import modulestore


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
    block_url = models.CharField(max_length=300)
    course_id = models.CharField(max_length=150)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    removed_answer = models.TextField(default="")

    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=datetime.now)

    @classmethod
    def actions_for_course(cls, course_id):
        return cls.objects.filter(course_id=course_id)

    @property
    def time_readable(self):

        return str(timezone.localtime(self.timestamp).replace(microsecond=0, tzinfo=None))

    @staticmethod
    def get_block_url(block_id):
        block_key = UsageKey.from_string(block_id)
        course_key = block_key.course_key
        store = modulestore()
        item = store.get_item(block_key)
        if item.category == "problem":
            section = item.get_parent().get_parent()
        elif item.category == "vertical":
            section = item.get_parent()
        else:
            return ""
        chapter = section.get_parent()
        return reverse('courseware_section', kwargs={
            'course_id': str(course_key),
            'section': section.location.block_id,
            'chapter': chapter.location.block_id
        })

    @classmethod
    def represent_queryset(cls, course_id):
        return cls.objects.filter(success=True, course_id=course_id).order_by('-timestamp')

    @classmethod
    def create(cls, instructor_username, student_username, block_id,
               course_id, action, removed_answer, success):
        print("CREATE")
        print(datetime.now())
        url = cls.get_block_url(block_id)
        return cls.objects.create(instructor_username=instructor_username,
                                  student_username=student_username,
                                  block_id=block_id,
                                  course_id=course_id,
                                  action=action,
                                  removed_answer=removed_answer,
                                  success=success,
                                  block_url=url
                                  )
