"""Grading tests"""
import unittest

from xmodule.graders import Score
from openedx.core.djangoapps.grading_policy.graders.weighted_subs import WeightedSubsectionsGrader
from openedx.core.djangoapps.grading_policy.graders.single_section import SingleSectionGrader
from openedx.core.djangoapps.grading_policy.graders.assignment_format import AssignmentFormatGrader


class GraderTest(unittest.TestCase):
    """Tests grader implementations"""
    empty_gradesheet = {
    }

    incomplete_gradesheet = {
        'Homework': [],
        'Lab': [],
        'Midterm': [],
    }

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

    def test_single_section_grader(self):
        midterm_grader = SingleSectionGrader("Midterm", "Midterm Exam")
        lab4_grader = SingleSectionGrader("Lab", "lab4")
        bad_lab_grader = SingleSectionGrader("Lab", "lab42")

        for graded in [midterm_grader.grade(self.empty_gradesheet),
                       midterm_grader.grade(self.incomplete_gradesheet),
                       bad_lab_grader.grade(self.test_gradesheet)]:
            self.assertEqual(len(graded['section_breakdown']), 1)
            self.assertEqual(graded['percent'], 0.0)

        graded = midterm_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.505)
        self.assertEqual(len(graded['section_breakdown']), 1)

        graded = lab4_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.2)
        self.assertEqual(len(graded['section_breakdown']), 1)

    def test_assignment_format_grader(self):
        homework_grader = AssignmentFormatGrader("Homework", 12, 2)
        no_drop_grader = AssignmentFormatGrader("Homework", 12, 0)
        # Even though the minimum number is 3, this should grade correctly when 7 assignments are found
        overflow_grader = AssignmentFormatGrader("Lab", 3, 2)
        lab_grader = AssignmentFormatGrader("Lab", 7, 3)

        # Test the grading of an empty gradesheet
        for graded in [homework_grader.grade(self.empty_gradesheet),
                       no_drop_grader.grade(self.empty_gradesheet),
                       homework_grader.grade(self.incomplete_gradesheet),
                       no_drop_grader.grade(self.incomplete_gradesheet)]:
            self.assertAlmostEqual(graded['percent'], 0.0)
            # Make sure the breakdown includes 12 sections, plus one summary
            self.assertEqual(len(graded['section_breakdown']), 12 + 1)

        graded = homework_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.11)  # 100% + 10% / 10 assignments
        self.assertEqual(len(graded['section_breakdown']), 12 + 1)

        graded = no_drop_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.0916666666666666)  # 100% + 10% / 12 assignments
        self.assertEqual(len(graded['section_breakdown']), 12 + 1)

        graded = overflow_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.8880952380952382)  # 100% + 10% / 5 assignments
        self.assertEqual(len(graded['section_breakdown']), 7 + 1)

        graded = lab_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.9226190476190477)
        self.assertEqual(len(graded['section_breakdown']), 7 + 1)

    def test_assignment_format_grader_on_single_section_entry(self):
        midterm_grader = AssignmentFormatGrader("Midterm", 1, 0)
        # Test the grading on a section with one item:
        for graded in [midterm_grader.grade(self.empty_gradesheet),
                       midterm_grader.grade(self.incomplete_gradesheet)]:
            self.assertAlmostEqual(graded['percent'], 0.0)
            # Make sure the breakdown includes just the one summary
            self.assertEqual(len(graded['section_breakdown']), 0 + 1)
            self.assertEqual(graded['section_breakdown'][0]['label'], 'Midterm')

        graded = midterm_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.505)
        self.assertEqual(len(graded['section_breakdown']), 0 + 1)

    def test_weighted_subsections_grader(self):
        # First, a few sub graders
        homework_grader = AssignmentFormatGrader("Homework", 12, 2)
        lab_grader = AssignmentFormatGrader("Lab", 7, 3)
        # phasing out the use of SingleSectionGraders, and instead using AssignmentFormatGraders that
        # will act like SingleSectionGraders on single sections.
        midterm_grader = AssignmentFormatGrader("Midterm", 1, 0)

        weighted_grader = WeightedSubsectionsGrader([
            (homework_grader, homework_grader.category, 0.25, 0.0),
            (lab_grader, lab_grader.category, 0.25, 0.0),
            (midterm_grader, midterm_grader.category, 0.5, 0.0)
        ])

        over_one_weights_grader = WeightedSubsectionsGrader([
            (homework_grader, homework_grader.category, 0.5, 0.0),
            (lab_grader, lab_grader.category, 0.5, 0.0),
            (midterm_grader, midterm_grader.category, 0.5, 0.0)
        ])

        # The midterm should have all weight on this one
        zero_weights_grader = WeightedSubsectionsGrader([
            (homework_grader, homework_grader.category, 0.0, 0.0),
            (lab_grader, lab_grader.category, 0.0, 0.0),
            (midterm_grader, midterm_grader.category, 0.5, 0.0)
        ])

        # This should always have a final percent of zero
        all_zero_weights_grader = WeightedSubsectionsGrader([
            (homework_grader, homework_grader.category, 0.0, 0.0),
            (lab_grader, lab_grader.category, 0.0, 0.0),
            (midterm_grader, midterm_grader.category, 0.0, 0.0)
        ])

        failing_passing_grade_grader = WeightedSubsectionsGrader([
            (homework_grader, homework_grader.category, 0.25, 0.5),
            (lab_grader, lab_grader.category, 0.25, 0.5),
            (midterm_grader, midterm_grader.category, 0.5, 0.0)
        ])

        passing_grade_grader = WeightedSubsectionsGrader([
            (homework_grader, homework_grader.category, 0.25, 0.11),
            (lab_grader, lab_grader.category, 0.25, 0.5),
            (midterm_grader, midterm_grader.category, 0.5, 0.0)
        ])

        empty_grader = WeightedSubsectionsGrader([])

        graded = weighted_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.5106547619047619)
        self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
        self.assertEqual(len(graded['grade_breakdown']), 3)

        graded = over_one_weights_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.7688095238095238)
        self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
        self.assertEqual(len(graded['grade_breakdown']), 3)

        graded = zero_weights_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.2525)
        self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
        self.assertEqual(len(graded['grade_breakdown']), 3)

        graded = all_zero_weights_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.0)
        self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
        self.assertEqual(len(graded['grade_breakdown']), 3)

        graded = failing_passing_grade_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.5106547619047619)
        self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
        self.assertEqual(len(graded['grade_breakdown']), 3)

        expected = {
            'Homework': False,  # 11 < 50
            'Lab': True,  # 92.3 >= 50
            'Midterm': True,  # 50.5 >= 0
        }
        for section in graded['grade_breakdown']:
            self.assertEqual(
                section['is_passed'], expected[section['category']],
                '{category}: {value} != {expected}'.format(
                    category=section['category'], value=section['is_passed'], expected=expected[section['category']]
                )
            )
        # Should be False, because one of the sections is not passed.
        self.assertEqual(graded['sections_passed'], False)

        graded = passing_grade_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.5106547619047619)
        self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
        self.assertEqual(len(graded['grade_breakdown']), 3)

        expected = {
            'Homework': True,  # 11 >= 11
            'Lab': True,  # 92.3 >= 50
            'Midterm': True,  # 50.5 >= 0
        }
        for section in graded['grade_breakdown']:
            self.assertEqual(
                section['is_passed'], expected[section['category']],
                '{category}: {value} != {expected}'.format(
                    category=section['category'], value=section['is_passed'], expected=expected[section['category']]
                )
            )
        # Should be True, because all the sections are passed.
        self.assertEqual(graded['sections_passed'], True)

        for graded in [weighted_grader.grade(self.empty_gradesheet),
                       weighted_grader.grade(self.incomplete_gradesheet),
                       zero_weights_grader.grade(self.empty_gradesheet),
                       all_zero_weights_grader.grade(self.empty_gradesheet)]:
            self.assertAlmostEqual(graded['percent'], 0.0)
            self.assertEqual(len(graded['section_breakdown']), (12 + 1) + (7 + 1) + 1)
            self.assertEqual(len(graded['grade_breakdown']), 3)

        graded = empty_grader.grade(self.test_gradesheet)
        self.assertAlmostEqual(graded['percent'], 0.0)
        self.assertEqual(len(graded['section_breakdown']), 0)
        self.assertEqual(len(graded['grade_breakdown']), 0)
