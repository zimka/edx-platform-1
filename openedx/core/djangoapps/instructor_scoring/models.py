import json

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from functools import wraps

from courseware.models import StudentModule
from certificates.models import CertificateWhitelist
from xmodule_django.models import UsageKeyField
from opaque_keys.edx.keys import UsageKey


class StudentGradeOverwrite(models.Model):
    """
    Instructor's overwrite for student's problem grade. Actually changes value of grade.
    On object's deletion original grade is restored. Doesn't store history but can be
    overridden again without lose of original grade.
    """
    #student_module = models.OneToOneField(StudentModule, on_delete=models.DO_NOTHING)

    user = models.ForeignKey(User)
    location = UsageKeyField(max_length=255)
    course_id = models.CharField(max_length=255)
    original_grade = models.FloatField(default=0)
    current_grade = models.FloatField(default=0)

    @classmethod
    def get_module(cls, student, location):
        if location.block_type == 'problem':
            try:
                return StudentModule.objects.get(module_state_key=location, student=student)
            except StudentModule.DoesNotExist:
                return None
        elif location.block_type == 'openassessment':
            try:
                return OraStudentModule.get(module_state_key=location, student=student)
            except OraStudentModule.DoesNotExistError:
                return None
        else:
            return TypeError("Can overwrite only problem or open response assessment, not '{}'".format(location.block_type))

    @classmethod
    def overwrite_student_grade(cls, location, student, grade):
        try:
            module = cls.get_module(student, location)
        except TypeError as e:
            return _(e.message), None

        if not module:
            return _("User haven't started task yet"), None

        if grade > module.max_grade:
            return _("Grade '{}' is higher than max_grade for this task: '{}'".format(grade, module.max_grade)), None
        if grade < 0:
            return _("Grade is lower than zero"), None
        if module.done == 'i':  # means "Incomplete"
            return _("Student haven't finished task yet"), None
        overwrite, created = StudentGradeOverwrite.objects.get_or_create(
            user=student, location=location, course_id=str(location.course_key)
        )
        overwrite.current_grade = grade
        if created:
            overwrite.original_grade = module.grade
        module.grade = grade
        module.save()
        overwrite.save()
        return "", overwrite

    @classmethod
    def get_overwrite(cls, location, user):
        try:
            overwrite = StudentGradeOverwrite.objects.get(user=user, location=location)
            return overwrite
        except StudentGradeOverwrite.DoesNotExist:
            return

    @classmethod
    def get_course_overwrites(cls, course_id):
        return StudentGradeOverwrite.objects.filter(course_id=course_id)
#    def save(self, *args, **kwargs):
#        if not self.pk and self.student_module.grade:
#            self.original_grade = self.student_module.grade
#        return super(StudentGradeOverwrite, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        module = self.get_module(self.user, self.location)
        #module = self.student_module
        module.grade = self.original_grade
        module.save()
        return super(StudentGradeOverwrite, self).delete(*args, **kwargs)

    def __str__(self):
        str_loc = str(self.location)
        str_obj = "{}: {} -> {}, {}".format(self.user.username, self.original_grade,
                                         self.current_grade, str_loc
        )
        return str_obj
    @classmethod
    def serialize(cls, obj):
        """Returns string that can be later unserialized"""
        if not isinstance(obj, cls):
            raise TypeError("Expected {} class, got {}".format(cls.__name__, type(obj).__name__))
        return "{}__{}".format(obj.user.username, str(obj.location))

    @classmethod
    def deserialize(cls, obj):
        """Returns string that can be later unserialized"""
        username, usage_id = obj.split("__")
        user = User.objects.get(username=username)
        location = UsageKey.from_string(usage_id)
        student_grade_overwrite = cls.objects.get(user=user, location=location)
        return student_grade_overwrite


from submissions.models import StudentItem, ScoreSummary
from student.models import anonymous_id_for_user


class OraStudentModule(object):
    """
    Interface to scores for OpenResponseAssessment. Mimics StudentModule interface.
    Raises LookupeError if ora score doesn't exist for user and location
    """
    DoesNotExistError = LookupError("No ora score for this user")

    def __init__(self, user, ora_location):
        self.user = user
        self.location = ora_location
        self.module_type =  u'openassessment'
        if ora_location.block_type != self.module_type:
            raise TypeError("OraOverwrite got non 'openassessment' location: '{}'".format(ora_location.block_type))

        course_key = self.location.course_key
        an_user_id = anonymous_id_for_user(self.user, course_key)
        score_summaries = ScoreSummary.objects.filter(
            student_item__item_id=str(self.location),
            student_item__student_id=an_user_id,
        ).select_related('latest')
        if len(score_summaries) < 1: # We don't need interface without object, catch it elsewhere
            raise self.DoesNotExistError

        if len(score_summaries) > 1:  # Something is really wrong here
            raise RuntimeError("More than one score summary, can't work with it")

        self.ora_score = score_summaries[0].latest

    @property
    def max_grade(self):
        return self.ora_score.points_possible

    @property
    def grade(self):
        return self.ora_score.points_earned

    @grade.setter
    def grade(self, value):
        self.ora_score.points_earned = value

    def save(self):
        self.ora_score.save()

    @property
    def done(self):
        """Needed only to mimic StudentModule interface, for any OraStudentModule ora module is finished actually"""
        return "f" #finished

    @classmethod
    def get(cls, module_state_key, student):
        obj = cls(user=student, ora_location=module_state_key)
        return obj


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
    whitelist = models.ForeignKey(CertificateWhitelist)

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
        course_id = str(course.id)
        old_grade_summary = dict((k,v) for k,v in grade_summary.items())
        try:
            scro = StudentCourseResultOverride.objects.get(student=student, course_id=course_id)
        except StudentCourseResultOverride.DoesNotExist:
            scro = None
        if not scro:
            return grade_summary
        grade_breakdown = grade_summary['grade_breakdown']
        new_grade_breakdown = []
        updated_sections = []
        for num, _section in enumerate(grade_breakdown):
            section = grade_breakdown[num]
            if (section['category'] in scro.passed_sections) or ('all' in scro.passed_sections):
                if not section['is_passed']:
                    section['is_passed'] = True
                    updated_sections.append(section['category'])
            new_grade_breakdown.append(section)
        grade_summary['grade_breakdown'] = new_grade_breakdown
        percent = grade_summary['percent'] + scro.added_percent
        grade_summary['percent'] = percent if percent < 1. else 1.
        grade_summary['grade'] = 'Pass'
        return grade_summary

    def delete(self, *args, **kwargs):
        self.whitelist.whitelist = False
        self.whitelist.save()
        return super(StudentCourseResultOverride, self).delete(*args, **kwargs)

    @classmethod
    def override_student_course_result(cls, student, course, percent, passed_sections='all'):
        if passed_sections == 'all':
            passed_sections = ['all']
        if percent > 1:
            percent = 1.

        override, created = cls.objects.get_or_create(student=student, course_id=str(course.id))
        override.passed_sections = passed_sections
        override.added_percent = percent
        if created:
            whitelist, created = CertificateWhitelist.objects.get_or_create(user=student, course_id=course.id)
            whitelist.whitelist = True
            whitelist.save()
            override.whitelist = whitelist
        override.save()


def course_result_override(func):
    """
    Use this decorator for openedx.core.djangoapps.grading_policy.sequentUal/vertical.py: *Some*Grading.grade
    Must be before staticmethod i.e. @staticmethod@course_result_override@
    :param func:
    :return:
    """
    @wraps(func)
    def wrapped(student, course, *args, **kwargs):
        grade_summary = func(student, course, *args, **kwargs)
        grade_summary = StudentCourseResultOverride.update_grader_result(student, course, grade_summary)
        return grade_summary
    return wrapped