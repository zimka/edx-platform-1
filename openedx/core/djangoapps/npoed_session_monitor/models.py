import logging
from django.db import models
from django.db import IntegrityError
from django.core.cache import cache
from edx_proctoring.models import ProctoredExamStudentAttempt

from .utils import ExamSessionSet
log = logging.getLogger(__name__)


class ExamSessionSetField(models.Field):
    """
    This field saves ExamSessionSet in serialized form
    """
    description = "Sessions that were registered during the exam"

    def __init__(self, *args, **kwargs):
        if not kwargs.get("default", None):
            kwargs['default'] = ExamSessionSet()
        super(ExamSessionSetField, self).__init__(*args, **kwargs)

    def get_internal_type(self):
        return 'TextField'

    def from_db_value(self, value, expression, connection, context):
        return self.to_python(value)

    def to_python(self, value):
        if isinstance(value, ExamSessionSet):
            return value
        if value is None:
            return ExamSessionSet()
        return ExamSessionSet.from_json(value)

    def get_prep_value(self, value=None):
        if (value is None) or (value == ""):
            value = ExamSessionSet()
        if not isinstance(value, ExamSessionSet):
            raise IntegrityError(
                "got non-ExamSessionSet arg in get_prep_value: {}, {}".format(str(value), str(type(value)))
            )
        return value.to_json()


class SuspiciousExamAttempt(models.Model):
    """
    Record of suspicious exam, for which several user sessions were observed.
    """
    #TODO: Currently exam attempt deletion leads to SuspiciousExamAttempt deletion

    exam_attempt = models.OneToOneField(ProctoredExamStudentAttempt)
    exam_sessions = ExamSessionSetField()

    def __unicode__(self):
        return "SuspiciousExamAttempt<" + str(self.exam_attempt.proctored_exam) + "|" + str(self.exam_attempt.user) + "|"+str(self.exam_sessions) +">"


class ExamSessionSetStorage(object):
    """
    Storage for exam sessions sets. It uses both cache and db.
    When we want to check if given session was already seen, we are taking ExamSessionSet from cache.
    If we save new ExamSessionSet and it is_suspicious, we also push it to database.
    """
    # TODO: There is a case when our monitoring fails.
    # If we have already observed one session, then cache is lost somehow, and then we see new session,
    # we won't be able to understand that there are two different session, and cheating will go unpunished.

    CACHE_KEY = "ExamSessionSet.{attempt_pk}"

    @classmethod
    def get(cls, attempt_pk):
        cache_key = cls.CACHE_KEY.format(attempt_pk=attempt_pk)
        exam_session_set = cache.get(cache_key)
        if not exam_session_set:
            return None
        return ExamSessionSet.from_json(exam_session_set)

    @classmethod
    def set(cls, attempt_pk, exam_session_set):
        # .set should be called quite rare, so it is safe to pull exam from db every time
        exam_attempt = ProctoredExamStudentAttempt.objects.get(pk=attempt_pk)
        if exam_session_set.is_suspicious():
            model, created = SuspiciousExamAttempt.objects.get_or_create(exam_attempt=exam_attempt)
            saved_exam_session_set = model.exam_sessions
            # It's unlikely but possible, that cache was somehow lost, but we have saved data
            # to db earlier. In this case we want to merge new session and update db
            total_session_set = saved_exam_session_set + exam_session_set
            model.exam_sessions = total_session_set
            model.save()
            log.info("Suspicious behavior was observed for user {} at exam {}".format(
                exam_attempt.user,
                exam_attempt.proctored_exam)
            )

        # double exam length
        timeout_seconds = 2 * (exam_attempt.allowed_time_limit_mins * 60)

        cache_key = cls.CACHE_KEY.format(attempt_pk=attempt_pk)
        cache.set(cache_key, exam_session_set.to_json(), timeout_seconds)
