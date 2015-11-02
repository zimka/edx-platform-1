"""
This file contains some tests for Instructor Task Django app with grading by verticals enabled.
lms/djangoapps/instructor_task/tests/test_integration.py
python ./manage.py lms test --verbosity=1 \
openedx/core/djangoapps/grading_policy/tests/test_instructor_task_integration.py --traceback --settings=test
"""
import json
import unittest
from django.test.utils import override_settings
from django.conf import settings
from celery.states import FAILURE  # pylint: disable=import-error, no-name-in-module
from lms.djangoapps.instructor_task.tests.test_base import InstructorTaskModuleTestCase
from openedx.core.djangoapps.util.testing import TestConditionalContent
from mock import patch
from instructor_task.models import InstructorTask
from instructor_task.tasks_helper import upload_grades_csv
from openedx.core.djangoapps.user_api.tests.factories import UserCourseTagFactory
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from xmodule.partitions.partitions import UserPartition, Group
from instructor_task.tests.test_base import TestReportMixin, OPTION_1, OPTION_2

from student.tests.factories import CourseEnrollmentFactory, UserFactory


@unittest.skipIf(settings._SYSTEM == 'cms', 'Test for lms')  # pylint: disable=protected-access
@override_settings(
    GRADING_TYPE='vertical', ASSIGNMENT_GRADER='WeightedAssignmentFormatGrader'
)
class TestConditionalContentVertical(TestConditionalContent):
    """
    Base mixin that prepares testind data for grading by verticals logic.
    """
    def setUp(self):
        """
        Set up a course with graded problems within a split test.

        Course hierarchy is as follows (modeled after how split tests
        are created in studio):
        -> course
            -> chapter
                -> vertical (graded)
                    -> split_test
                        -> vertical (Group A)
                            -> problem
                        -> vertical (Group B)
                            -> problem
        """
        super(TestConditionalContentVertical, self).setUp()

        # Create user partitions
        self.user_partition_group_a = 0
        self.user_partition_group_b = 1
        self.partition = UserPartition(
            0,
            'first_partition',
            'First Partition',
            [
                Group(self.user_partition_group_a, 'Group A'),
                Group(self.user_partition_group_b, 'Group B')
            ]
        )

        # Create course with group configurations and grading policy
        self.course = CourseFactory.create(
            user_partitions=[self.partition],
            grading_policy={
                "GRADER": [{
                    "type": "Homework",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "HW",
                    "passing_grade": 0,
                    "weight": 1.0
                }]
            }
        )
        chapter = ItemFactory.create(parent_location=self.course.location,
                                     display_name='Chapter')

        # add a sequence to the course to which the problems can be added
        self.problem_section = ItemFactory.create(
            parent_location=chapter.location,
            category='vertical',
            metadata={'graded': True, 'format': 'Homework', 'weight': 0.8},
            display_name=self.TEST_SECTION_NAME)

        ItemFactory.create(
            parent_location=chapter.location,
            category='vertical',
            metadata={'graded': True, 'format': 'Homework', 'weight': 0.2},
            display_name="New Section"
        )

        # Create users and partition them
        self.student_a = UserFactory.create(username='student_a',
                                            email='student_a@example.com')
        CourseEnrollmentFactory.create(user=self.student_a,
                                       course_id=self.course.id)
        self.student_b = UserFactory.create(username='student_b',
                                            email='student_b@example.com')
        CourseEnrollmentFactory.create(user=self.student_b,
                                       course_id=self.course.id)

        UserCourseTagFactory(
            user=self.student_a,
            course_id=self.course.id,
            key='xblock.partition_service.partition_{0}'.format(
                self.partition.id),  # pylint: disable=no-member
            value=str(self.user_partition_group_a)
        )
        UserCourseTagFactory(
            user=self.student_b,
            course_id=self.course.id,
            key='xblock.partition_service.partition_{0}'.format(
                self.partition.id),  # pylint: disable=no-member
            value=str(self.user_partition_group_b)
        )
        # Create the split test and child vertical containers
        vertical_a_url = self.course.id.make_usage_key('vertical',
                                                       'split_test_vertical_a')
        vertical_b_url = self.course.id.make_usage_key('vertical',
                                                       'split_test_vertical_b')
        self.split_test = ItemFactory.create(
            parent_location=self.problem_section.location,
            category='split_test',
            display_name='Split Test',
            user_partition_id=self.partition.id,  # pylint: disable=no-member
            group_id_to_child={str(index): url for index, url in
                               enumerate([vertical_a_url, vertical_b_url])}
        )
        self.vertical_a = ItemFactory.create(
            parent_location=self.split_test.location,
            category='vertical',
            display_name='Group A problem container',
            location=vertical_a_url
        )
        self.vertical_b = ItemFactory.create(
            parent_location=self.split_test.location,
            category='vertical',
            display_name='Group B problem container',
            location=vertical_b_url
        )


@unittest.skipIf(settings._SYSTEM == 'cms', 'Test for lms')  # pylint: disable=protected-access
class TestGradeReportConditionalContent(TestReportMixin, TestConditionalContentVertical, InstructorTaskModuleTestCase):
    """
    Test grade report in cases where there are problems contained within split tests.
    """

    def _assert_task_failure(self, entry_id, task_type, problem_url_name, expected_message):
        """Confirm that expected values are stored in InstructorTask on task failure."""
        instructor_task = InstructorTask.objects.get(id=entry_id)
        self.assertEqual(instructor_task.task_state, FAILURE)
        self.assertEqual(instructor_task.requester.username, 'instructor')
        self.assertEqual(instructor_task.task_type, task_type)
        task_input = json.loads(instructor_task.task_input)
        self.assertFalse('student' in task_input)
        self.assertEqual(task_input['problem_url'],
                         InstructorTaskModuleTestCase.problem_location(problem_url_name).to_deprecated_string())
        status = json.loads(instructor_task.task_output)
        self.assertEqual(status['exception'], 'ZeroDivisionError')
        self.assertEqual(status['message'], expected_message)
        # check status returned:
        status = InstructorTaskModuleTestCase.get_task_status(instructor_task.task_id)
        self.assertEqual(status['message'], expected_message)

    def verify_csv_task_success(self, task_result):
        """
        Verify that all students were successfully graded by
        `upload_grades_csv`.

        Arguments:
            task_result (dict): Return value of `upload_grades_csv`.
        """
        self.assertDictContainsSubset(
            {'attempted': 2, 'succeeded': 2, 'failed': 0}, task_result)

    def verify_grades_in_csv(self, students_grades,
                             ignore_other_columns=False):
        """
        Verify that the grades CSV contains the expected grades data.

        Arguments:
            students_grades (iterable): An iterable of dictionaries,
                where each dict maps a student to another dict
                representing their grades we expect to see in the CSV.
                For example: [student_a: {'grade': 1.0, 'HW': 1.0}]
        """

        def merge_dicts(*dicts):
            """
            Return the union of dicts

            Arguments:
                dicts: tuple of dicts
            """
            return dict([item for d in dicts for item in d.items()])

        def user_partition_group(user):
            """Return a dict having single key with value equals to students group in partition"""
            group_config_hdr_tpl = 'Experiment Group ({})'
            return {
                group_config_hdr_tpl.format(self.partition.name): self.partition.scheme.get_group_for_user(
                    self.course.id, user, self.partition, track_function=None  # pylint: disable=E1101
                ).name
            }

        self.verify_rows_in_csv(
            [
                merge_dicts(
                    {'id': str(student.id), 'username': student.username, 'email': student.email},
                    grades, user_partition_group(student)
                )
                for student_grades in students_grades for student, grades in
                student_grades.iteritems()
            ], ignore_other_columns=ignore_other_columns
        )

    def test_both_groups_problems(self):
        """
        Verify that grade export works when each user partition
        receives (different) problems.  Each user's grade on their
        particular problem should show up in the grade report.
        """
        problem_a_url = 'problem_a_url'
        problem_b_url = 'problem_b_url'
        self.define_option_problem(problem_a_url, parent=self.vertical_a)
        self.define_option_problem(problem_b_url, parent=self.vertical_b)
        # student A will get 100%, student B will get 50% because
        # OPTION_1 is the correct option, and OPTION_2 is the
        # incorrect option
        self.submit_student_answer(self.student_a.username, problem_a_url,
                                   [OPTION_1, OPTION_1])
        self.submit_student_answer(self.student_b.username, problem_b_url,
                                   [OPTION_1, OPTION_2])

        with patch('instructor_task.tasks_helper._get_current_task'):
            result = upload_grades_csv(None, None, self.course.id, None,
                                       'graded')
            self.verify_csv_task_success(result)
            self.verify_grades_in_csv(
                [
                    {self.student_a: {'grade': '0.8', 'HW 01': '1.0', 'HW 02': '0.0', 'HW Avg': '0.8'}},
                    {self.student_b: {'grade': '0.4', 'HW 01': '0.5', 'HW 02': '0.0', 'HW Avg': '0.4'}}
                ],
                ignore_other_columns=True
            )

    def test_one_group_problem(self):
        """
        Verify that grade export works when only the Group A user
        partition receives a problem.  We expect to see a column for
        the homework where student_a's entry includes their grade, and
        student b's entry shows a 0.
        """
        problem_a_url = 'problem_a_url'
        self.define_option_problem(problem_a_url, parent=self.vertical_a)

        self.submit_student_answer(self.student_a.username, problem_a_url,
                                   [OPTION_1, OPTION_1])

        with patch('instructor_task.tasks_helper._get_current_task'):
            result = upload_grades_csv(None, None, self.course.id, None,
                                       'graded')
            self.verify_csv_task_success(result)
            self.verify_grades_in_csv(
                [
                    {self.student_a: {'grade': '0.8', 'HW 01': '1.0', 'HW 02': '0.0', 'HW Avg': '0.8'}},
                    {self.student_b: {'grade': '0.0', 'HW 01': '0.0', 'HW 02': '0.0', 'HW Avg': '0.0'}}
                ],
                ignore_other_columns=True
            )
