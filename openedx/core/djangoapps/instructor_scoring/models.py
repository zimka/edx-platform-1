import json
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from courseware.models import StudentModule


class StudentGradeOverride(models.Model):
    """
    Instructor's override for student's problem grade. Actually changes value of grade.
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


class StudentCourseResultOverride(models.Model):
    """
    Allows instructor to add points to overall course score.
    Doesn't actually change any student's result. Should be watched at
    grading module.
    """
    student = models.ForeignKey(User)
    course_id = models.CharField(max_length=100)
    added_percent = models.FloatField()
    passed_sections = models.CharField(max_length=256)

    def __setattr__(self, attrname, val):
        if attrname == "passed_section":
            val = json.dumps(val)
        super(StudentCourseResultOverride, self).__setattr__(attrname, val)

    def __getattr__(self, attrname):
        val = super(StudentCourseResultOverride, self).__getattr__(attrname)
        if attrname == "passed_section":
            val = json.loads(val)
        return val

    @classmethod
    def update_grader_result(cls, student, course, grade_summary):
        """
        Updates grade_summary if override for course-student exists.
        """
        course_id = course.id

        try:
            scro = StudentCourseResultOverride.objects.get(student=student, course_id=course_id)
        except StudentGradeOverride.DoesNotExist:
            scro = None
        if not scro:
            return "", grade_summary
        grade_breakdown = grade_summary['grade_breakdown']
        new_grade_breakdown = []
        updated_sections = []
        for num, _section in enumerate(grade_breakdown):
            section = grade_breakdown[num]
            if section['category'] in scro.passed_sections:
                if not section['is_passed']:
                    section['is_passed'] = True
                    updated_sections.append(section['category'])
            new_grade_breakdown.append(section)
        grade_summary['grade_breakdown'] = new_grade_breakdown
        percent = grade_summary['percent'] + scro.added_percent
        grade_summary['percent'] = percent if percent < 1. else 1.
        grade_summary['grade'] = 'Pass'
        return "Updated sections:{}".format(",".join(x for x in updated_sections)), grade_summary
