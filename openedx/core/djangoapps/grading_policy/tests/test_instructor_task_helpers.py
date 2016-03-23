# -*- coding: utf-8 -*-
"""
This file contains some tests for Instructor Task Django app with grading by verticals enabled.
lms/djangoapps/instructor_task/tests/test_tasks_helper.py
python ./manage.py lms test --verbosity=1 openedx/core/djangoapps/grading_policy/tests/test_instructor_task_helpers.py /
--traceback --settings=test
"""
import unittest

from openedx.core.djangoapps.content.course_structures.signals import listen_for_course_publish
from xmodule.modulestore.django import SignalHandler

import ddt
from django.conf import settings
from mock import patch
from django.test.utils import override_settings

from instructor_task.tests.test_base import TestReportMixin, InstructorTaskModuleTestCase, TEST_SECTION_NAME
from xmodule.modulestore.tests.factories import ItemFactory
from instructor_task.models import ReportStore
from instructor_task.tasks_helper import upload_problem_grade_report
from openedx.core.djangoapps.util.testing import ContentGroupTestCase


def disconnect_course_published_event():  # pylint: disable=invalid-name
    """Disconnect course_published event."""
    # If we don't disconnect then tests are getting failed in test_crud.py
    SignalHandler.course_published.disconnect(listen_for_course_publish)


@unittest.skipIf(settings._SYSTEM == 'cms', 'Test for lms')  # pylint: disable=protected-access
@override_settings(GRADING_TYPE='vertical', ASSIGNMENT_GRADER='WeightedAssignmentFormatGrader')
@ddt.ddt
class TestProblemGradeReport(TestReportMixin, InstructorTaskModuleTestCase):
    """
    Test that the problem CSV generation works.
    """
    def setUp(self):
        # For some reason, `listen_for_course_publish` is not called when we run
        # all (paver test_system -s cms) tests, If we run only run this file then tests run fine.
        SignalHandler.course_published.connect(listen_for_course_publish)

        super(TestProblemGradeReport, self).setUp()
        self.initialize_course()
        # Add unicode data to CSV even though unicode usernames aren't
        # technically possible in openedx.
        self.student_1 = self.create_student(u'üser_1')
        self.student_2 = self.create_student(u'üser_2')
        self.csv_header_row = [u'Student ID', u'Email', u'Username',
                               u'Final Grade']

        self.addCleanup(disconnect_course_published_event)

    def add_course_content(self):
        """
        Add a chapter and a sequential to the current course.
        """
        # Add a chapter to the course
        chapter = ItemFactory.create(
            parent_location=self.course.location,
            display_name=TEST_SECTION_NAME
        )

        # add a sequence to the course to which the problems can be added
        self.problem_section = ItemFactory.create(  # pylint: disable=attribute-defined-outside-init
            parent_location=chapter.location,
            category='sequential',
            display_name=TEST_SECTION_NAME
        )

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_no_problems(self, _get_current_task):
        """
        Verify that we see no grade information for a course with no graded
        problems.
        """
        result = upload_problem_grade_report(None, None, self.course.id, None,
                                             'graded')
        self.assertDictContainsSubset(
            {'action_name': 'graded', 'attempted': 2, 'succeeded': 2,
             'failed': 0}, result)
        self.verify_rows_in_csv([
            dict(zip(
                self.csv_header_row,
                [unicode(self.student_1.id), self.student_1.email,
                 self.student_1.username, '1.0']
            )),
            dict(zip(
                self.csv_header_row,
                [unicode(self.student_2.id), self.student_2.email,
                 self.student_2.username, '1.0']
            ))
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_single_problem(self, _get_current_task):
        vertical = ItemFactory.create(
            parent_location=self.problem_section.location,
            category='vertical',
            metadata={'graded': True, 'format': 'Homework', 'weight': 0.8},
            display_name='Problem Vertical'
        )
        ItemFactory.create(
            parent_location=self.problem_section.location,
            category='vertical',
            metadata={'graded': True, 'format': 'Homework', 'weight': 0.2},
            display_name='Problem Vertical 2'
        )
        self.define_option_problem(u'Pröblem1', parent=vertical)

        self.submit_student_answer(self.student_1.username, u'Pröblem1',
                                   ['Option 1'])
        result = upload_problem_grade_report(None, None, self.course.id, None,
                                             'graded')
        self.assertDictContainsSubset(
            {'action_name': 'graded', 'attempted': 2, 'succeeded': 2,
             'failed': 0}, result)
        problem_name = u'Homework 1: Problem Vertical - Pröblem1'
        header_row = self.csv_header_row + [problem_name + ' (Earned)',
                                            problem_name + ' (Possible)']
        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    unicode(self.student_1.id),
                    self.student_1.email,
                    self.student_1.username,
                    #    ('Homework', percent=0.4, weight=0.15, total=0.06)
                    #    ('Lab', percent=1.0, weight=0.15, total=0.15)
                    #    ('Midterm Exam', percent=1.0, weight=0.3, total=0.3)
                    #    ('Final Exam', percent=1.0, weight=0.4, total=0.4)
                    '0.91', '1.0', '2.0']
            )),
            dict(zip(
                header_row,
                [
                    unicode(self.student_2.id),
                    self.student_2.email,
                    self.student_2.username,
                    #    ('Homework', percent=0.0, weight=0.15, total=0.0)
                    #    ('Lab', percent=1.0, weight=0.15, total=0.15)
                    #    ('Midterm Exam', percent=1.0, weight=0.3, total=0.3)
                    #    ('Final Exam', percent=1.0, weight=0.4, total=0.4)
                    '0.85', 'N/A', 'N/A'
                ]
            ))
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    @patch('instructor_task.tasks_helper.iterate_grades_for')
    @ddt.data(u'Cannöt grade student', '')
    def test_grading_failure(self, error_message, mock_iterate_grades_for, _mock_current_task):
        """
        Test that any grading errors are properly reported in the progress
        dict and uploaded to the report store.
        """
        # mock an error response from `iterate_grades_for`
        student = self.create_student(u'username', u'student@example.com')
        mock_iterate_grades_for.return_value = [
            (student, {}, error_message)
        ]
        result = upload_problem_grade_report(None, None, self.course.id, None,
                                             'graded')
        self.assertDictContainsSubset(
            {'attempted': 1, 'succeeded': 0, 'failed': 1}, result)

        report_store = ReportStore.from_config(config_name='GRADES_DOWNLOAD')
        self.assertTrue(any('grade_report_err' in item[0] for item in
                            report_store.links_for(self.course.id)))
        self.verify_rows_in_csv([
            {
                u'Student ID': unicode(student.id),
                u'Email': student.email,
                u'Username': student.username,
                u'error_msg': error_message if error_message else "Unknown error"
            }
        ])


@unittest.skipIf(settings._SYSTEM == 'cms', 'Test for lms')  # pylint: disable=protected-access
@override_settings(GRADING_TYPE='vertical', ASSIGNMENT_GRADER='WeightedAssignmentFormatGrader')
class TestProblemReportCohortedContent(TestReportMixin, ContentGroupTestCase, InstructorTaskModuleTestCase):
    """
    Test the problem report on a course that has cohorted content.
    """
    def setUp(self):
        # For some reason, `listen_for_course_publish` is not called when we run
        # all (paver test_system -s cms) tests, If we run only run this file then tests run fine.
        SignalHandler.course_published.connect(listen_for_course_publish)

        super(TestProblemReportCohortedContent, self).setUp()
        # contstruct cohorted problems to work on.
        self.add_course_content()
        vertical = ItemFactory.create(
            parent_location=self.problem_section.location,
            category='vertical',
            metadata={'graded': True, 'format': u'Homework', 'weight': 0.8},
            display_name='Problem Vertical'
        )
        ItemFactory.create(
            parent_location=self.problem_section.location,
            category='vertical',
            metadata={'graded': True, 'format': u'Homework', 'weight': 0.2},
            display_name='Problem Vertical 2'
        )
        self.define_option_problem(
            u"Pröblem0",
            parent=vertical,
            group_access={self.course.user_partitions[0].id: [
                self.course.user_partitions[0].groups[0].id]}
        )
        self.define_option_problem(
            u"Pröblem1",
            parent=vertical,
            group_access={self.course.user_partitions[0].id: [
                self.course.user_partitions[0].groups[1].id]}
        )

        self.addCleanup(disconnect_course_published_event)

    def test_cohort_content(self):
        self.submit_student_answer(self.alpha_user.username, u'Pröblem0',
                                   ['Option 1', 'Option 1'])
        resp = self.submit_student_answer(self.alpha_user.username,
                                          u'Pröblem1',
                                          ['Option 1', 'Option 1'])
        self.assertEqual(resp.status_code, 404)

        resp = self.submit_student_answer(self.beta_user.username, u'Pröblem0',
                                          ['Option 1', 'Option 2'])
        self.assertEqual(resp.status_code, 404)
        self.submit_student_answer(self.beta_user.username, u'Pröblem1',
                                   ['Option 1', 'Option 2'])

        with patch('instructor_task.tasks_helper._get_current_task'):
            result = upload_problem_grade_report(None, None, self.course.id,
                                                 None, 'graded')
            self.assertDictContainsSubset(
                {'action_name': 'graded', 'attempted': 4, 'succeeded': 4,
                 'failed': 0}, result
            )

        problem_names = [u'Homework 1: Problem Vertical - Pröblem0',
                         u'Homework 1: Problem Vertical - Pröblem1']
        header_row = [u'Student ID', u'Email', u'Username', u'Final Grade']
        for problem in problem_names:
            header_row += [problem + ' (Earned)', problem + ' (Possible)']

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    unicode(self.staff_user.id),
                    self.staff_user.email,
                    self.staff_user.username, u'0.0', u'N/A', u'N/A', u'N/A',
                    u'N/A'
                ]
            )),
            dict(zip(
                header_row,
                [
                    unicode(self.alpha_user.id),
                    self.alpha_user.email,
                    self.alpha_user.username,
                    u'0.8', u'2.0', u'2.0', u'N/A', u'N/A'
                ]
            )),
            dict(zip(
                header_row,
                [
                    unicode(self.beta_user.id),
                    self.beta_user.email,
                    self.beta_user.username,
                    u'0.4', u'N/A', u'N/A', u'1.0', u'2.0'
                ]
            )),
            dict(zip(
                header_row,
                [
                    unicode(self.non_cohorted_user.id),
                    self.non_cohorted_user.email,
                    self.non_cohorted_user.username,
                    u'0.0', u'N/A', u'N/A', u'N/A', u'N/A'
                ]
            )),
        ])

    def add_course_content(self):
        """
        Add a chapter and a sequential to the current course.
        """
        # Add a chapter to the course
        chapter = ItemFactory.create(
            parent_location=self.course.location,
            display_name=TEST_SECTION_NAME
        )

        # add a sequence to the course to which the problems can be added
        self.problem_section = ItemFactory.create(
            parent_location=chapter.location,
            category='sequential',
            display_name=TEST_SECTION_NAME
        )
