from django.db import models


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
