from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from courseware.models import StudentModule
from xmodule_django.models import UsageKeyField
from opaque_keys.edx.keys import UsageKey
from submissions.models import ScoreSummary
from student.models import anonymous_id_for_user


class StudentGradeOverwrite(models.Model):
    """
    Instructor's overwrite for student's problem grade. Actually changes value of grade.
    On object's deletion original grade is restored. Doesn't store history but can be
    overridden again without lose of original grade.
    """

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
            return TypeError(
                "Can overwrite only problem or open response assessment, not '{}'".format(location.block_type))

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

    def delete(self, *args, **kwargs):
        module = self.get_module(self.user, self.location)
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


class OraStudentModule(object):
    """
    Interface to scores for OpenResponseAssessment. Mimics StudentModule interface.
    Raises LookupeError if ora score doesn't exist for user and location
    """
    DoesNotExistError = LookupError("No ora score for this user")

    def __init__(self, user, ora_location):
        self.user = user
        self.location = ora_location
        self.module_type = u'openassessment'
        if ora_location.block_type != self.module_type:
            raise TypeError("OraOverwrite got non 'openassessment' location: '{}'".format(ora_location.block_type))

        course_key = self.location.course_key
        an_user_id = anonymous_id_for_user(self.user, course_key)
        score_summaries = ScoreSummary.objects.filter(
            student_item__item_id=str(self.location),
            student_item__student_id=an_user_id,
        ).select_related('latest')
        if len(score_summaries) < 1:  # We don't need interface without object, catch it elsewhere
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
        return "f"  # finished

    @classmethod
    def get(cls, module_state_key, student):
        obj = cls(user=student, ora_location=module_state_key)
        return obj
