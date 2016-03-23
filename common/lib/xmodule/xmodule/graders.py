import abc
import inspect
import logging
import random
import sys

from django.conf import settings
from collections import namedtuple
from stevedore.extension import ExtensionManager

log = logging.getLogger("edx.courseware")

# This is a tuple for holding scores, either from problems or sections.
# Section either indicates the name of the problem or the name of the section
Score = namedtuple("Score", "earned possible graded section module_id")


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


def aggregate_scores(scores, section_name="summary"):
    """
    scores: A list of Score objects
    returns: A tuple (all_total, graded_total).
        all_total: A Score representing the total score summed over all input scores
        graded_total: A Score representing the score summed over all graded input scores
    """
    total_correct_graded = sum(score.earned for score in scores if score.graded)
    total_possible_graded = sum(score.possible for score in scores if score.graded)

    total_correct = sum(score.earned for score in scores)
    total_possible = sum(score.possible for score in scores)

    #regardless of whether or not it is graded
    all_total = Score(
        total_correct,
        total_possible,
        False,
        section_name,
        None
    )
    #selecting only graded things
    graded_total = Score(
        total_correct_graded,
        total_possible_graded,
        True,
        section_name,
        None
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
    with AssignmentFormatGrader's or SingleSectionGrader's as subsections will be
    generated. Every dictionary should contain the parameters for making either a
    AssignmentFormatGrader or SingleSectionGrader, in addition to a 'weight' key.
    """
    if isinstance(conf, CourseGrader):
        return conf

    subgraders = []
    for subgraderconf in conf:
        subgraderconf = subgraderconf.copy()
        weight = subgraderconf.pop("weight", 0)
        passing_grade = subgraderconf.pop("passing_grade", 0)
        # NOTE: 'name' used to exist in SingleSectionGrader. We are deprecating SingleSectionGrader
        # and converting everything into an AssignmentFormatGrader by adding 'min_count' and
        # 'drop_count'. AssignmentFormatGrader does not expect 'name', so if it appears
        # in bad_args, go ahead remove it (this causes no errors). Eventually, SingleSectionGrader
        # should be completely removed.
        name = 'name'
        try:
            if 'min_count' in subgraderconf:
                #This is an AssignmentFormatGrader
                subgrader_class = get_grader(settings.ASSIGNMENT_GRADER)
            elif name in subgraderconf:
                #This is an SingleSectionGrader
                subgrader_class = get_grader('SingleSectionGrader')
            else:
                raise ValueError("Configuration has no appropriate grader class.")

            bad_args = invalid_args(subgrader_class.__init__, subgraderconf)
            # See note above concerning 'name'.
            if bad_args.issuperset({name}):
                bad_args = bad_args - {name}
                del subgraderconf[name]
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
    - grade_breakdown: This is a list of dictionaries which provide details on the contributions
    of the final percentage grade. This is a higher level breakdown, for when the grade is constructed
    of a few very large sections (such as Homeworks, Labs, a Midterm, and a Final). The format for
    a grade_breakdown is explained below. This section is optional.

    A dictionary in the section_breakdown list has the following keys:
    percent: A float percentage for the section.
    label: A short string identifying the section. Preferably fixed-length. E.g. "HW  3".
    detail: A string explanation of the score. E.g. "Homework 1 - Ohms Law - 83% (5/6)"
    category: A string identifying the category. Items with the same category are grouped together
    in the display (for example, by color).
    prominent: A boolean value indicating that this section should be displayed as more prominent
    than other items.

    A dictionary in the grade_breakdown list has the following keys:
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
