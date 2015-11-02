"""
This file contains some tests for CCX Django app with grading by verticals enabled.
lms/djangoapps/ccx/tests/test_views.py
"""

import datetime
import unittest
from django.conf import settings
from lms.djangoapps.ccx.tests.test_views import iter_blocks
import pytz
from mock import patch, MagicMock
from nose.plugins.attrib import attr

from capa.tests.response_xml_factory import StringResponseXMLFactory
from ccx.overrides import override_field_for_ccx
from ccx.tests.factories import CcxFactory
from ccx.tests.factories import CcxMembershipFactory
from courseware.courses import get_course_by_id  # pyline: disable=import-error
from courseware.field_overrides import OverrideFieldData  # pylint: disable=import-error
from courseware.tests.factories import StudentModuleFactory  # pylint: disable=import-error
from courseware.tests.helpers import LoginEnrollmentTestCase  # pylint: disable=import-error
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from django.test import RequestFactory
from edxmako.shortcuts import render_to_response  # pylint: disable=import-error
from student.roles import CourseCcxCoachRole  # pylint: disable=import-error
from student.tests.factories import (  # pylint: disable=import-error
    AdminFactory, CourseEnrollmentFactory, UserFactory,
)

from xmodule.x_module import XModuleMixin
from xmodule.modulestore.tests.django_utils import (
    ModuleStoreTestCase,
    TEST_DATA_SPLIT_MODULESTORE)
from xmodule.modulestore.tests.factories import (
    CourseFactory,
    ItemFactory,
)
from ccx_keys.locator import CCXLocator


def intercept_renderer(path, context):
    """
    Intercept calls to `render_to_response` and attach the context dict to the
    response for examination in unit tests.
    """
    # I think Django already does this for you in their TestClient, except
    # we're bypassing that by using edxmako.  Probably edxmako should be
    # integrated better with Django's rendering and event system.
    response = render_to_response(path, context)
    response.mako_context = context
    response.mako_template = path
    return response


def ccx_dummy_request():
    """
    Returns dummy request object for CCX coach tab test
    """
    factory = RequestFactory()
    request = factory.get('ccx_coach_dashboard')
    request.user = MagicMock()

    return request


GET_CHILDREN = XModuleMixin.get_children


def patched_get_children(self, usage_key_filter=None):
    """Emulate system tools that mask courseware not visible to students"""

    def iter_children():
        """skip children not visible to students"""
        for child in GET_CHILDREN(self, usage_key_filter=usage_key_filter):
            child._field_data_cache = {}  # pylint: disable=protected-access
            if not child.visible_to_staff_only:
                yield child

    return list(iter_children())


@unittest.skipIf(settings._SYSTEM == 'cms', 'Test for lms')  # pylint: disable=protected-access
@override_settings(
    FIELD_OVERRIDE_PROVIDERS=('ccx.overrides.CustomCoursesForEdxOverrideProvider',),
    GRADING_TYPE='vertical', ASSIGNMENT_GRADER='WeightedAssignmentFormatGrader'
)
@attr('shard_1')
@patch('xmodule.x_module.XModuleMixin.get_children', patched_get_children, spec=True)
class TestCCXGradesVertical(ModuleStoreTestCase, LoginEnrollmentTestCase):
    """
    Tests for Custom Courses views.
    """
    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def setUp(self):
        """
        Set up a course with graded problems.

        Course hierarchy is as follows:
        -> course
            -> chapter
                -> vertical (graded)
                    -> problem
                    -> problem
        """
        super(TestCCXGradesVertical, self).setUp()
        self.course = course = CourseFactory.create(enable_ccx=True)
        # Create instructor account
        self.coach = coach = AdminFactory.create()
        self.client.login(username=coach.username, password="test")

        # Create a course outline
        self.mooc_start = start = datetime.datetime(
            2010, 5, 12, 2, 42, tzinfo=pytz.UTC)
        chapter = ItemFactory.create(start=start, parent=course)
        verticals = [
            ItemFactory.create(
                parent=chapter,
                category="vertical",
                metadata={'graded': True, 'format': 'Homework', 'weight': 0.5}
            ),
            ItemFactory.create(
                parent=chapter,
                category="vertical",
                metadata={'graded': True, 'format': 'Homework', 'weight': 0.2}
            ),
            ItemFactory.create(
                parent=chapter,
                category="vertical",
                metadata={'graded': True, 'format': 'Homework', 'weight': 0.2}
            ),
            ItemFactory.create(
                parent=chapter,
                category="vertical",
                metadata={'graded': True, 'format': 'Homework', 'weight': 0.1}
            ),
            ItemFactory.create(
                parent=chapter,
                category="vertical",
                metadata={'graded': True, 'format': 'Homework', 'weight': 1.0}
            ),
        ]
        # pylint: disable=unused-variable
        problems = [
            [
                ItemFactory.create(
                    parent=section,
                    category="problem",
                    data=StringResponseXMLFactory().build_xml(answer='foo'),
                    metadata={'rerandomize': 'always'}
                ) for _ in xrange(4)
            ] for section in verticals
        ]

        # Create CCX
        role = CourseCcxCoachRole(course.id)
        role.add_users(coach)
        ccx = CcxFactory(course_id=course.id, coach=self.coach)

        # Apparently the test harness doesn't use LmsFieldStorage, and I'm not
        # sure if there's a way to poke the test harness to do so.  So, we'll
        # just inject the override field storage in this brute force manner.
        OverrideFieldData.provider_classes = None
        # pylint: disable=protected-access
        for block in iter_blocks(course):
            block._field_data = OverrideFieldData.wrap(coach, course, block._field_data)
            new_cache = {'tabs': [], 'discussion_topics': []}
            if 'grading_policy' in block._field_data_cache:
                new_cache['grading_policy'] = block._field_data_cache['grading_policy']
            block._field_data_cache = new_cache

        def cleanup_provider_classes():
            """
            After everything is done, clean up by un-doing the change to the
            OverrideFieldData object that is done during the wrap method.
            """
            OverrideFieldData.provider_classes = None

        self.addCleanup(cleanup_provider_classes)

        # override course grading policy and make last section invisible to students
        override_field_for_ccx(ccx, course, 'grading_policy', {
            'GRADER': [
                {'drop_count': 0,
                 'min_count': 2,
                 'short_label': 'HW',
                 'type': 'Homework',
                 'passing_grade': 0,
                 'weight': 1}
            ],
            'GRADE_CUTOFFS': {'Pass': 0.75},
        })
        override_field_for_ccx(
            ccx, verticals[-1], 'visible_to_staff_only', True)

        # create a ccx locator and retrieve the course structure using that key
        # which emulates how a student would get access.
        self.ccx_key = CCXLocator.from_course_locator(course.id, ccx.id)
        self.course = get_course_by_id(self.ccx_key)

        self.student = student = UserFactory.create()
        CourseEnrollmentFactory.create(user=student, course_id=self.course.id)
        CcxMembershipFactory(ccx=ccx, student=student, active=True)

        # create grades for self.student as if they'd submitted the ccx
        for chapter in self.course.get_children():
            for i, vertical in enumerate(chapter.get_children()):
                for j, problem in enumerate(vertical.get_children()):
                    # if not problem.visible_to_staff_only:
                    StudentModuleFactory.create(
                        grade=1 if i < j else 0,
                        max_grade=1,
                        student=self.student,
                        course_id=self.course.id,
                        module_state_key=problem.location
                    )

        self.client.login(username=coach.username, password="test")

    @patch('ccx.views.render_to_response', intercept_renderer)
    def test_gradebook(self):
        self.course.enable_ccx = True
        url = reverse(
            'ccx_gradebook',
            kwargs={'course_id': self.ccx_key}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        student_info = response.mako_context['students'][0]  # pylint: disable=no-member
        self.assertEqual(student_info['grade_summary']['percent'], 0.53)
        self.assertAlmostEqual(
            student_info['grade_summary']['grade_breakdown'][0]['percent'], 0.525
        )
        self.assertEqual(
            len(student_info['grade_summary']['section_breakdown']), 5)

    def test_grades_csv(self):
        self.course.enable_ccx = True
        url = reverse(
            'ccx_grades_csv',
            kwargs={'course_id': self.ccx_key}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        headers, row = (
            row.strip().split(',') for row in
            response.content.strip().split('\n')
        )
        data = dict(zip(headers, row))
        self.assertEqual(data['HW 01'], '0.75')
        self.assertEqual(data['HW 02'], '0.5')
        self.assertEqual(data['HW 03'], '0.25')
        self.assertEqual(data['HW 04'], '0.0')
        self.assertAlmostEqual(float(data['HW Avg']), 0.525)
        self.assertTrue('HW 05' not in data)

    @patch('courseware.views.render_to_response', intercept_renderer)
    def test_student_progress(self):
        self.course.enable_ccx = True
        patch_context = patch('courseware.views.get_course_with_access')
        get_course = patch_context.start()
        get_course.return_value = self.course
        self.addCleanup(patch_context.stop)

        self.client.login(username=self.student.username, password="test")
        url = reverse(
            'progress',
            kwargs={'course_id': self.ccx_key}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        grades = response.mako_context['grade_summary']  # pylint: disable=no-member
        self.assertEqual(grades['percent'], 0.53)
        self.assertAlmostEqual(grades['grade_breakdown'][0]['percent'], 0.525)
        self.assertEqual(len(grades['section_breakdown']), 5)
