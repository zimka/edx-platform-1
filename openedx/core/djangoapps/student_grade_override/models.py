from django.db import models
from django.utils.translation import ugettext as _
from courseware.models import StudentModule


class StudentGradeOverride(models.Model):
    """
    Instructors override for student's problem grade. Actually changes value of grade.
    On object's deletion original grade is restored. Doesn't store history but can be
    overridden again without lose of original grade.
    """
    student_module = models.OneToOneField(StudentModule, on_delete=models.DO_NOTHING)
    original_grade = models.FloatField(default=0)
    current_grade = models.FloatField(default=0)

    @classmethod
    def override_student_grade(cls, location, student, grade):
        try:
            module = StudentModule.objects.get(module_state_key=location, student=student)
        except StudentModule.DoesNotExist:
            module = None
        if not module:
            return _("User haven't started task yet"), None
        if grade > module.max_grade:
            return _("Grade is higher than max_grade for this task"), None
        if grade < 0:
            return _("Grade is lower than zero"), None
        if module.done == 'i':  # means "Incomplete"
            return _("Student haven't finished task yet"), None
        override, created = StudentGradeOverride.objects.get_or_create(student_module=module)
        override.current_grade = grade
        if created:
            override.original_grade = module.grade
        module.grade = grade
        module.save()
        override.save()
        override, created = StudentGradeOverride.objects.get_or_create(student_module=module)
        return "", override

    @classmethod
    def get_override(cls, location, user):
        try:
            module = StudentModule.objects.get(module_state_key=location, student=user)
            if not module:
                return
            override = StudentGradeOverride.objects.get(student_module=module)
            return override
        except (StudentModule.DoesNotExist, StudentGradeOverride.DoesNotExist) :
            return

    def save(self, *args, **kwargs):
        if not self.pk:
            self.original_grade = self.student_module.grade
        return super(StudentGradeOverride, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        module = self.student_module
        module.grade = self.original_grade
        module.save()
        return super(StudentGradeOverride, self).delete(*args, **kwargs)
