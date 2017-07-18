from lazy import lazy
from logging import getLogger

from courseware.model_data import ScoresClient
from openedx.core.lib.grade_utils import is_score_higher_or_equal
from student.models import anonymous_id_for_user
from submissions import api as submissions_api

from lms.djangoapps.grades.config import should_persist_grades, assume_zero_if_absent
from lms.djangoapps.grades.models import PersistentVerticalGrade
from lms.djangoapps.grades.scores import possibly_scored
from .course_data import CourseData
from .vertical_grade import VerticalGrade, ZeroVerticalGrade


log = getLogger(__name__)


class VerticalGradeFactory(object):
    """
    Factory for Vertical Grades.
    """
    def __init__(self, student, course=None, course_structure=None, course_data=None):
        self.student = student
        self.course_data = course_data or CourseData(student, course=course, structure=course_structure)

        self._cached_vertical_grades = None
        self._unsaved_vertical_grades = []

    def create(self, vertical, read_only=False):
        """
        Returns the VerticalGrade object for the student and vertic.

        If read_only is True, doesn't save any updates to the grades.
        """
        self._log_event(
            log.debug, u"create, read_only: {0}, vertical: {1}".format(read_only, vertical.location), vertical,
        )

        vertical_grade = self._get_bulk_cached_grade(vertical)
        if not vertical_grade:
            if assume_zero_if_absent(self.course_data.course_key):
                vertical_grade = ZeroVerticalGrade(vertical, self.course_data)
            else:
                vertical_grade = VerticalGrade(vertical).init_from_structure(
                    self.student, self.course_data.structure, self._submissions_scores, self._csm_scores,
                )
                if should_persist_grades(self.course_data.course_key):
                    if read_only:
                        self._unsaved_vertical_grades.append(vertical_grade)
                    else:
                        grade_model = vertical_grade.create_model(self.student)
                        self._update_saved_vertical_grade(vertical.location, grade_model)
        return vertical_grade

    def bulk_create_unsaved(self):
        """
        Bulk creates all the unsaved vertical_grades to this point.
        """
        VerticalGrade.bulk_create_models(self.student, self._unsaved_vertical_grades, self.course_data.course_key)
        self._unsaved_vertical_grades = []

    def update(self, vertical, only_if_higher=None):
        """
        Updates the VerticalGrade object for the student and vertical.
        """
        # Save ourselves the extra queries if the course does not persist
        # vertical grades.
        self._log_event(log.warning, u"update, vertical: {}".format(vertical.location), vertical)

        calculated_grade = VerticalGrade(vertical).init_from_structure(
            self.student, self.course_data.structure, self._submissions_scores, self._csm_scores,
        )

        if should_persist_grades(self.course_data.course_key):
            if only_if_higher:
                try:
                    grade_model = PersistentVerticalGrade.read_grade(self.student.id, vertical.location)
                except PersistentVerticalGrade.DoesNotExist:
                    pass
                else:
                    orig_vertical_grade = VerticalGrade(vertical).init_from_model(
                        self.student, grade_model, self.course_data.structure, self._submissions_scores, self._csm_scores,
                    )
                    if not is_score_higher_or_equal(
                            orig_vertical_grade.graded_total.earned,
                            orig_vertical_grade.graded_total.possible,
                            calculated_grade.graded_total.earned,
                            calculated_grade.graded_total.possible,
                    ):
                        return orig_vertical_grade

            grade_model = calculated_grade.update_or_create_model(self.student)
            self._update_saved_vertical_grade(vertical.location, grade_model)

        return calculated_grade

    @lazy
    def _csm_scores(self):
        """
        Lazily queries and returns all the scores stored in the user
        state (in CSM) for the course, while caching the result.
        """
        scorable_locations = [block_key for block_key in self.course_data.structure if possibly_scored(block_key)]
        return ScoresClient.create_for_locations(self.course_data.course_key, self.student.id, scorable_locations)

    @lazy
    def _submissions_scores(self):
        """
        Lazily queries and returns the scores stored by the
        Submissions API for the course, while caching the result.
        """
        anonymous_user_id = anonymous_id_for_user(self.student, self.course_data.course_key)
        return submissions_api.get_scores(str(self.course_data.course_key), anonymous_user_id)

    def _get_bulk_cached_grade(self, vertical):
        """
        Returns the student's VerticalGrade for the vertical,
        while caching the results of a bulk retrieval for the
        course, for future access of other verticals.
        Returns None if not found.
        """
        if should_persist_grades(self.course_data.course_key):
            saved_vertical_grades = self._get_bulk_cached_vertical_grades()
            vertical_grade = saved_vertical_grades.get(vertical.location)
            if vertical_grade:
                return VerticalGrade(vertical).init_from_model(
                    self.student, vertical_grade, self.course_data.structure, self._submissions_scores, self._csm_scores,
                )

    def _get_bulk_cached_vertical_grades(self):
        """
        Returns and caches (for future access) the results of
        a bulk retrieval of all vertical grades in the course.
        """
        if self._cached_vertical_grades is None:
            self._cached_vertical_grades = {
                record.full_usage_key: record
                for record in PersistentVerticalGrade.bulk_read_grades(self.student.id, self.course_data.course_key)
            }
        return self._cached_vertical_grades

    def _update_saved_vertical_grade(self, vertical_usage_key, vertical_model):
        """
        Updates (or adds) the vertical grade for the given
        vertical usage key in the local cache, iff the cache
        is populated.
        """
        if self._cached_vertical_grades is not None:
            self._cached_vertical_grades[vertical_usage_key] = vertical_model

    def _log_event(self, log_func, log_statement, vertical):
        """
        Logs the given statement, for this instance.
        """
        log_func(u"Grades: SGF.{}, course: {}, version: {}, edit: {}, user: {}".format(
            log_statement,
            self.course_data.course_key,
            getattr(vertical, 'course_version', None),
            getattr(vertical, 'subtree_edited_on', None),
            self.student.id,
        ))
