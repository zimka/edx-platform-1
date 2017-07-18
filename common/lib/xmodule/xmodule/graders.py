"""
Code used to calculate learner grades.
"""

from __future__ import division

import abc
from collections import OrderedDict
import inspect
import logging
import random
import sys

from django.conf import settings
from stevedore.extension import ExtensionManager

log = logging.getLogger("edx.courseware")


class UnrecognizedGraderError(Exception):
    """An error occurred when grader is unavailable."""
    pass


def get_grader(grader_type):
    """Returns grader by the `grader_type(str)`."""
    extension = ExtensionManager(namespace='openedx.graders')
    try:
        return extension[grader_type].plugin
    except KeyError:
        raise UnrecognizedGraderError("Unrecognized grader `{0}`".format(grader_type))


class ScoreBase(object):
    """
    Abstract base class for encapsulating fields of values scores.
    Field common to all scores include:
        graded (boolean) - whether or not this module is graded
        attempted (boolean) - whether the module was attempted
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, graded, attempted):
        self.graded = graded
        self.attempted = attempted

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return u"{class_name}({fields})".format(class_name=self.__class__.__name__, fields=self.__dict__)


class ProblemScore(ScoreBase):
    """
    Encapsulates the fields of a Problem's score.
    In addition to the fields in ScoreBase, also includes:
        raw_earned (float) - raw points earned on this problem
        raw_possible (float) - raw points possible to earn on this problem
        weighted_earned = earned (float) - weighted value of the points earned
        weighted_possible = possible (float) - weighted possible points on this problem
        weight (float) - weight of this problem
    """
    def __init__(self, raw_earned, raw_possible, weighted_earned, weighted_possible, weight, *args, **kwargs):
        super(ProblemScore, self).__init__(*args, **kwargs)
        self.raw_earned = float(raw_earned) if raw_earned is not None else None
        self.raw_possible = float(raw_possible) if raw_possible is not None else None
        self.earned = float(weighted_earned) if weighted_earned is not None else None
        self.possible = float(weighted_possible) if weighted_possible is not None else None
        self.weight = weight


class AggregatedScore(ScoreBase):
    """
    Encapsulates the fields of a Subsection's score.
    In addition to the fields in ScoreBase, also includes:
        tw_earned = earned - total aggregated sum of all weighted earned values
        tw_possible = possible - total aggregated sum of all weighted possible values
    """
    def __init__(self, tw_earned, tw_possible, *args, **kwargs):
        super(AggregatedScore, self).__init__(*args, **kwargs)
        self.earned = float(tw_earned) if tw_earned is not None else None
        self.possible = float(tw_possible) if tw_possible is not None else None


def float_sum(iterable):
    """
    Sum the elements of the iterable, and return the result as a float.
    """
    return float(sum(iterable))


def aggregate_scores(scores):
    """
    scores: A list of ScoreBase objects
    returns: A tuple (all_total, graded_total).
        all_total: A ScoreBase representing the total score summed over all input scores
        graded_total: A ScoreBase representing the score summed over all graded input scores
    """
    total_correct_graded = float_sum(score.earned for score in scores if score.graded)
    total_possible_graded = float_sum(score.possible for score in scores if score.graded)
    any_attempted_graded = any(score.attempted for score in scores if score.graded)

    total_correct = float_sum(score.earned for score in scores)
    total_possible = float_sum(score.possible for score in scores)
    any_attempted = any(score.attempted for score in scores)

    # regardless of whether it is graded
    all_total = AggregatedScore(total_correct, total_possible, False, any_attempted)

    # selecting only graded things
    graded_total = AggregatedScore(
        total_correct_graded, total_possible_graded, True, any_attempted_graded,
    )

    return all_total, graded_total


def invalid_args(func, argdict):
    """
    Given a function and a dictionary of arguments, returns a set of arguments
    from argdict that aren't accepted by func
    """
    args, _, keywords, _ = inspect.getargspec(func)
    if keywords:
        return set()  # All accepted
    return set(argdict) - set(args)


def grader_from_conf(conf):
    """
    This creates a CourseGrader from a configuration (such as in course_settings.py).
    The conf can simply be an instance of CourseGrader, in which case no work is done.
    More commonly, the conf is a list of dictionaries. A WeightedSubsectionsGrader
    with AssignmentFormatGraders will be generated. Every dictionary should contain
    the parameters for making an AssignmentFormatGrader, in addition to a 'weight' key.
    """
    if isinstance(conf, CourseGrader):
        return conf

    subgraders = []
    for subgraderconf in conf:
        subgraderconf = subgraderconf.copy()
        weight = subgraderconf.pop("weight", 0)
        passing_grade = subgraderconf.pop("passing_grade", 0)
        try:
            if 'min_count' in subgraderconf:
                #This is an AssignmentFormatGrader
                subgrader_class = get_grader(settings.ASSIGNMENT_GRADER)
            else:
                raise ValueError("Configuration has no appropriate grader class.")

            bad_args = invalid_args(subgrader_class.__init__, subgraderconf)
            if len(bad_args) > 0:
                log.warning("Invalid arguments for a subgrader: %s", bad_args)
                for key in bad_args:
                    del subgraderconf[key]

            subgrader = subgrader_class(**subgraderconf)
            subgraders.append((subgrader, subgrader.category, weight, passing_grade))

        except (TypeError, ValueError) as error:
            # Add info and re-raise
            msg = ("Unable to parse grader configuration:\n    " +
                   str(subgraderconf) +
                   "\n    Error was:\n    " + str(error))
            raise ValueError(msg), None, sys.exc_info()[2]

    return get_grader(settings.COURSE_GRADER)(subgraders)


class CourseGrader(object):
    """
    A course grader takes the totaled scores for each graded section (that a student has
    started) in the course. From these scores, the grader calculates an overall percentage
    grade. The grader should also generate information about how that score was calculated,
    to be displayed in graphs or charts.

    A grader has one required method, grade(), which is passed a grade_sheet. The grade_sheet
    contains scores for all graded section that the student has started. If a student has
    a score of 0 for that section, it may be missing from the grade_sheet. The grade_sheet
    is keyed by section format. Each value is a list of Score namedtuples for each section
    that has the matching section format.

    The grader outputs a dictionary with the following keys:
    - percent: Contains a float value, which is the final percentage score for the student.
    - section_breakdown: This is a list of dictionaries which provide details on sections
    that were graded. These are used for display in a graph or chart. The format for a
    section_breakdown dictionary is explained below.
    - grade_breakdown: This is a dict of dictionaries, keyed by category, which provide details on
    the contributions of the final percentage grade. This is a higher level breakdown, for when the
    grade is constructed of a few very large sections (such as Homeworks, Labs, a Midterm, and a Final).
    The format for a grade_breakdown is explained below. This section is optional.

    A dictionary in the section_breakdown list has the following keys:
    percent: A float percentage for the section.
    label: A short string identifying the section. Preferably fixed-length. E.g. "HW  3".
    detail: A string explanation of the score. E.g. "Homework 1 - Ohms Law - 83% (5/6)"
    category: A string identifying the category. Items with the same category are grouped together
    in the display (for example, by color).
    prominent: A boolean value indicating that this section should be displayed as more prominent
    than other items.

    A dictionary in the grade_breakdown dict has the following keys:
    percent: A float percentage in the breakdown. All percents should add up to the final percentage.
    detail: A string explanation of this breakdown. E.g. "Homework - 10% of a possible 15%"
    category: A string identifying the category. Items with the same category are grouped together
    in the display (for example, by color).


    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def grade(self, grade_sheet, generate_random_scores=False):
        '''Given a grade sheet, return a dict containing grading information'''
        raise NotImplementedError
