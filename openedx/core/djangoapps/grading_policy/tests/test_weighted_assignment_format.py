"""
Tests for WeightedAssignmentFormatGrader.
python ./manage.py lms test --verbosity=1 \
openedx/core/djangoapps/grading_policy/graders/tests/test_weighted_assignment_format.py --traceback --settings=test
"""
import unittest

from openedx.core.djangoapps.grading_policy.vertical import WeightedScore
from openedx.core.djangoapps.grading_policy.graders.weighted_assignment_format import WeightedAssignmentFormatGrader


class WeightedAssignmentFormatGraderTest(unittest.TestCase):
    """Tests grader implementations."""
    empty_gradesheet = {}

    incomplete_gradesheet = {
        'Homework': [],
        'Lab': [],
        'Midterm': [],
    }

    test_gradesheet = {
        'Homework': [
            WeightedScore(earned=2, possible=20.0, graded=True, section='hw1', module_id=None, weight=0.2),
            WeightedScore(earned=16, possible=16.0, graded=True, section='hw2', module_id=None, weight=0.8)
        ],
        # The dropped scores should be from the assignments that don't exist yet

        'Lab': [
            WeightedScore(earned=1, possible=2.0, graded=True, section='lab1', module_id=None, weight=0.1),  # Dropped
            WeightedScore(earned=1, possible=1.0, graded=True, section='lab2', module_id=None, weight=0.2),
            WeightedScore(earned=1, possible=1.0, graded=True, section='lab3', module_id=None, weight=0.3),
            WeightedScore(earned=5, possible=25.0, graded=True, section='lab4', module_id=None, weight=0.3),  # Dropped
            WeightedScore(earned=5, possible=6.0, graded=True, section='lab5', module_id=None, weight=0.1)  # Dropped
        ],

        'Midterm': [
            WeightedScore(earned=50.5, possible=100, graded=True, section="Midterm Exam", module_id=None, weight=1.0)
        ],
    }

    def test_weighted_assignment_format_grader(self):
        homework_grader = WeightedAssignmentFormatGrader("Homework", 2, 1)
        no_drop_homework_grader = WeightedAssignmentFormatGrader("Homework", 2, 0)
        homework_overflow_grader = WeightedAssignmentFormatGrader("Homework", 12, 2)
        no_drop_grader = WeightedAssignmentFormatGrader("Homework", 12, 0)
        # Even though the minimum number is 3, this should grade correctly when 5 assignments are found
        overflow_grader = WeightedAssignmentFormatGrader("Lab", 3, 2)
        lab_grader = WeightedAssignmentFormatGrader("Lab", 5, 3)

        gradesheets = [
            homework_overflow_grader.grade(self.empty_gradesheet), no_drop_grader.grade(self.empty_gradesheet),
            homework_overflow_grader.grade(self.incomplete_gradesheet), no_drop_grader.grade(self.incomplete_gradesheet)
        ]
        # Test the grading of an empty gradesheet
        for graded in gradesheets:
            self.assertAlmostEqual(graded['percent'], 1.0)
            # Make sure the breakdown includes 12 sections, plus one summary
            self.assertEqual(len(graded['section_breakdown']), 12 + 1)

        graded = no_drop_homework_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.82)
        self.assertEqual(len(graded['section_breakdown']), 2 + 1)

        graded = homework_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 1.0)
        self.assertEqual(len(graded['section_breakdown']), 2 + 1)

        graded = homework_overflow_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], (2 * 0.2 / 20 + 0.8) / 1)  # 80% + 2% / 1 normalized_weight
        self.assertEqual(len(graded['section_breakdown']), 12 + 1)

        graded = no_drop_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], (2 * 0.2 / 20 + 0.8) / 1)  # 80% + 2% / 1 normalized_weight
        self.assertEqual(len(graded['section_breakdown']), 12 + 1)

        graded = overflow_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], (0.2 + 0.3 + 0.5 / 6) / (1 - 0.1 - 0.3))
        self.assertEqual(len(graded['section_breakdown']), 5 + 1)

        graded = lab_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], (0.2 + 0.3) / (1 - 0.1 - 0.3 - 0.1))
        self.assertEqual(len(graded['section_breakdown']), 5 + 1)

    def test_weighted_assignment_format_grader_on_single_section_entry(self):
        wrong_weight_gradesheet = {
            'Midterm': [
                WeightedScore(earned=0.5, possible=1, graded=True, section="Midterm Exam", module_id=None, weight=0.7)
            ],
        }
        midterm_grader = WeightedAssignmentFormatGrader("Midterm", 1, 0)
        wrong_weight_grader = WeightedAssignmentFormatGrader("Midterm", 1, 0)
        # Test the grading on a section with one item:
        for graded in [midterm_grader.grade(self.empty_gradesheet),
                       midterm_grader.grade(self.incomplete_gradesheet)]:
            self.assertAlmostEqual(graded['percent'], 1.0)
            # Make sure the breakdown includes just the one summary
            self.assertEqual(len(graded['section_breakdown']), 0 + 1)
            self.assertEqual(graded['section_breakdown'][0]['label'], 'Midterm')

        graded = midterm_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 50.5 / 100)  # 0.505
        self.assertEqual(len(graded['section_breakdown']), 0 + 1)

        graded = wrong_weight_grader.grade(wrong_weight_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.5 * 0.7 / 0.7)  # 0.5
        self.assertEqual(len(graded['section_breakdown']), 0 + 1)

    def test_corner_cases(self):
        over_one_weights_gradesheet = {
            'Lab': [
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw1', module_id=None, weight=0.5),
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw2', module_id=None, weight=0.5),
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw3', module_id=None, weight=0.5)
            ],
        }

        zero_weights_gradesheet = {
            'Lab': [
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw1', module_id=None, weight=0.0),
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw2', module_id=None, weight=0.0),
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw3', module_id=None, weight=0.5)
            ],
        }

        all_zero_weights_gradesheet = {
            'Lab': [
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw1', module_id=None, weight=0.0),
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw2', module_id=None, weight=0.0),
                WeightedScore(earned=1.0, possible=1.0, graded=True, section='hw3', module_id=None, weight=0.0)
            ],
        }

        over_one_weights_grader = WeightedAssignmentFormatGrader('Lab', 3, 0)
        # The midterm should have all weight on this one
        zero_weights_grader = WeightedAssignmentFormatGrader('Lab', 3, 0)
        # This should always have a final percent of zero
        all_zero_weights_grader = WeightedAssignmentFormatGrader('Lab', 3, 0)

        graded = over_one_weights_grader.grade(over_one_weights_gradesheet)
        self.assertAlmostEqual(graded['percent'], 1.0)
        self.assertEqual(len(graded['section_breakdown']), 3 + 1)

        graded = zero_weights_grader.grade(zero_weights_gradesheet)
        self.assertAlmostEqual(graded['percent'], 1.0)
        self.assertEqual(len(graded['section_breakdown']), 3 + 1)

        graded = all_zero_weights_grader.grade(all_zero_weights_gradesheet)
        self.assertAlmostEqual(graded['percent'], 1.0)
        self.assertEqual(len(graded['section_breakdown']), 3 + 1)
