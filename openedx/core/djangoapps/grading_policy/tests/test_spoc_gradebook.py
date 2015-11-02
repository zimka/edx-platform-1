"""
This file contains some tests for Instructor Django app with grading by verticals enabled.
lms/djangoapps/instructor/tests/test_spoc_gradebook.py
"""
import unittest
from django.test.utils import override_settings
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from django.conf import settings
from django.core.urlresolvers import reverse
from nose.plugins.attrib import attr
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from student.tests.factories import UserFactory, CourseEnrollmentFactory, AdminFactory
from capa.tests.response_xml_factory import StringResponseXMLFactory
from courseware.tests.factories import StudentModuleFactory
from xmodule.modulestore.django import modulestore

USER_COUNT = 11


@unittest.skipIf(settings._SYSTEM == 'cms', 'Test for lms')  # pylint: disable=protected-access
@attr('shard_1')
@override_settings(
    GRADING_TYPE='vertical', ASSIGNMENT_GRADER='WeightedAssignmentFormatGrader'
)
class TestGradebookVertical(ModuleStoreTestCase):
    """
    Test functionality of the spoc gradebook. Sets up a course with assignments and
    students who've scored various scores on these assignments. Base class for further
    gradebook tests.
    """
    grading_policy = None

    def setUp(self):
        super(TestGradebookVertical, self).setUp()

        instructor = AdminFactory.create()
        self.client.login(username=instructor.username, password='test')

        # remove the caches
        modulestore().request_cache = None
        modulestore().metadata_inheritance_cache_subsystem = None

        kwargs = {}
        if self.grading_policy is not None:
            kwargs['grading_policy'] = self.grading_policy

        self.course = CourseFactory.create(**kwargs)
        chapter = ItemFactory.create(
            parent_location=self.course.location,
            category="sequential",
        )
        section = ItemFactory.create(
            parent_location=chapter.location,
            category="vertical",
            metadata={'graded': True, 'format': 'Homework', 'weight': 0.8}
        )

        ItemFactory.create(
            parent_location=chapter.location,
            category="vertical",
            metadata={'graded': True, 'format': 'Homework', 'weight': 0.2}
        )

        self.users = [UserFactory.create() for _ in xrange(USER_COUNT)]

        for user in self.users:
            CourseEnrollmentFactory.create(user=user, course_id=self.course.id)

        for i in xrange(USER_COUNT - 1):
            category = "problem"
            item = ItemFactory.create(
                parent_location=section.location,
                category=category,
                data=StringResponseXMLFactory().build_xml(answer='foo'),
                metadata={'rerandomize': 'always'}
            )

            for j, user in enumerate(self.users):
                StudentModuleFactory.create(
                    grade=1 if i < j else 0,
                    max_grade=1,
                    student=user,
                    course_id=self.course.id,
                    module_state_key=item.location
                )

        self.response = self.client.get(reverse(
            'spoc_gradebook',
            args=(self.course.id.to_deprecated_string(),)
        ))

    def test_response_code(self):
        self.assertEquals(self.response.status_code, 200)


@unittest.skipIf(settings._SYSTEM == 'cms', 'Test for lms')  # pylint: disable=protected-access
@attr('shard_1')
class TestLetterCutoffPolicy(TestGradebookVertical):
    """
    Tests advanced grading policy (with letter grade cutoffs). Includes tests of
    UX display (color, etc).
    """
    grading_policy = {
        "GRADER": [
            {
                "type": "Homework",
                "min_count": 1,
                "drop_count": 0,
                "short_label": "HW",
                "passing_grade": 0,
                "weight": 1
            },
        ],
        "GRADE_CUTOFFS": {
            'A': .9,
            'B': .8,
            'C': .7,
            'D': .6,
        }
    }

    def test_styles(self):
        self.assertIn("grade_A {color:green;}", self.response.content)
        self.assertIn("grade_B {color:Chocolate;}", self.response.content)
        self.assertIn("grade_C {color:DarkSlateGray;}", self.response.content)
        self.assertIn("grade_D {color:DarkSlateGray;}", self.response.content)

    def test_assigned_grades(self):
        # One use at the top of the page [1]
        self.assertEquals(3, self.response.content.count('grade_A'))
        # One use at the top of the page [1]
        self.assertEquals(4, self.response.content.count('grade_B'))
        # One use at the top of the page [1]
        self.assertEquals(4, self.response.content.count('grade_C'))
        # One use at the top of the page [1]
        self.assertEquals(4, self.response.content.count('grade_D'))
        # One use at top of the page [1]
        self.assertEquals(20, self.response.content.count('grade_F'))
        # One use at the top of the page [1]
        self.assertEquals(15, self.response.content.count('grade_None'))


@attr('shard_1')
class TestPassingGradeVertical(TestGradebookVertical):
    """
    Tests advanced grading policy (with letter grade cutoffs and passing grades).
    """
    grading_policy = {
        "GRADER": [
            {
                "type": "Homework",
                "min_count": 1,
                "drop_count": 0,
                "short_label": "HW",
                "passing_grade": .8,
                "weight": 1
            },
        ],
        "GRADE_CUTOFFS": {
            'A': .9,
            'B': .8,
            'C': .7,
            'D': .6,
        }
    }

    def test_assigned_grades(self):
        self.assertEquals(2, self.response.content.count('grade_A'))
        self.assertEquals(3, self.response.content.count('grade_B'))
        # All other users don't reach passing grade
        self.assertEquals(42, self.response.content.count('grade_None'))
