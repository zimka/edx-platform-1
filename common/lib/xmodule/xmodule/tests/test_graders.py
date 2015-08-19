"""Grading tests"""
import unittest

from django.test.utils import override_settings
from xmodule import graders
from xmodule.graders import Score, aggregate_scores


class GradesheetTest(unittest.TestCase):
    '''Tests the aggregate_scores method'''

    def test_weighted_grading(self):
        scores = []
        Score.__sub__ = lambda me, other: (me.earned - other.earned) + (me.possible - other.possible)

        all_total, graded_total = aggregate_scores(scores)
        self.assertEqual(all_total, Score(earned=0, possible=0, graded=False, section="summary", module_id=None))
        self.assertEqual(graded_total, Score(earned=0, possible=0, graded=True, section="summary", module_id=None))

        scores.append(Score(earned=0, possible=5, graded=False, section="summary", module_id=None))
        all_total, graded_total = aggregate_scores(scores)
        self.assertEqual(all_total, Score(earned=0, possible=5, graded=False, section="summary", module_id=None))
        self.assertEqual(graded_total, Score(earned=0, possible=0, graded=True, section="summary", module_id=None))

        scores.append(Score(earned=3, possible=5, graded=True, section="summary", module_id=None))
        all_total, graded_total = aggregate_scores(scores)
        self.assertAlmostEqual(all_total, Score(earned=3, possible=10, graded=False, section="summary", module_id=None))
        self.assertAlmostEqual(
            graded_total, Score(earned=3, possible=5, graded=True, section="summary", module_id=None)
        )

        scores.append(Score(earned=2, possible=5, graded=True, section="summary", module_id=None))
        all_total, graded_total = aggregate_scores(scores)
        self.assertAlmostEqual(all_total, Score(earned=5, possible=15, graded=False, section="summary", module_id=None))
        self.assertAlmostEqual(
            graded_total, Score(earned=5, possible=10, graded=True, section="summary", module_id=None)
        )


@override_settings(ASSIGNMENT_GRADER="AssignmentFormatGrader", COURSE_GRADER='WeightedSubsectionsGrader')
class GraderTest(unittest.TestCase):
    '''Tests grader implementations'''
    test_gradesheet = {
        'Homework': [Score(earned=2, possible=20.0, graded=True, section='hw1', module_id=None),
                     Score(earned=16, possible=16.0, graded=True, section='hw2', module_id=None)],
        # The dropped scores should be from the assignments that don't exist yet

        'Lab': [Score(earned=1, possible=2.0, graded=True, section='lab1', module_id=None),  # Dropped
                Score(earned=1, possible=1.0, graded=True, section='lab2', module_id=None),
                Score(earned=1, possible=1.0, graded=True, section='lab3', module_id=None),
                Score(earned=5, possible=25.0, graded=True, section='lab4', module_id=None),  # Dropped
                Score(earned=3, possible=4.0, graded=True, section='lab5', module_id=None),  # Dropped
                Score(earned=6, possible=7.0, graded=True, section='lab6', module_id=None),
                Score(earned=5, possible=6.0, graded=True, section='lab7', module_id=None)],

        'Midterm': [Score(earned=50.5, possible=100, graded=True, section="Midterm Exam", module_id=None), ],
    }

    def test_grader_from_conf(self):

        # Confs always produce a graders.WeightedSubsectionsGrader, so we test this by repeating the test
        # in test_graders.WeightedSubsectionsGrader, but generate the graders with confs.

        weighted_grader = graders.grader_from_conf([
            {
                'type': "Homework",
                'min_count': 12,
                'drop_count': 2,
                'short_label': "HW",
                'weight': 0.25,
            },
            {
                'type': "Lab",
                'min_count': 7,
                'drop_count': 3,
                'category': "Labs",
                'weight': 0.25
            },
            {
                'type': "Midterm",
                'name': "Midterm Exam",
                'short_label': "Midterm",
                'weight': 0.5,
            },
        ])

        empty_grader = graders.grader_from_conf([])

        graded = weighted_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.5106547619047619)
        self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
        self.assertEqual(len(graded['grade_breakdown']), 3)

        graded = empty_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.0)
        self.assertEqual(len(graded['section_breakdown']), 0)
        self.assertEqual(len(graded['grade_breakdown']), 0)

        # Test that graders can also be used instead of lists of dictionaries
        homework_grader = graders.get_grader('AssignmentFormatGrader')("Homework", 12, 2)
        homework_grader2 = graders.grader_from_conf(homework_grader)

        graded = homework_grader2.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.11)
        self.assertEqual(len(graded['section_breakdown']), 12 + 1)

        # TODO: How do we test failure cases? The parser only logs an error when
        # it can't parse something. Maybe it should throw exceptions?
