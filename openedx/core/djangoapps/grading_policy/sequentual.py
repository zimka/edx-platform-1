# Compute grades using real division, with no integer truncation
from __future__ import division

import json
import logging
import random
from collections import defaultdict
from functools import partial

import dogstats_wrapper as dog_stats_api
from django.conf import settings
from django.core.cache import cache
from django.test.client import RequestFactory
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import BlockUsageLocator

from openedx.core.lib.gating import api as gating_api
from courseware import courses
from courseware.access import has_access
from courseware.model_data import FieldDataCache, ScoresClient
from openedx.core.djangoapps.signals.signals import GRADES_UPDATED
from student.models import anonymous_id_for_user
from util.db import outer_atomic
from util.module_utils import yield_dynamic_descriptor_descendants
from xmodule import graders
from xmodule.exceptions import UndefinedContext
from xmodule.graders import Score
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from courseware.models import StudentModule
from courseware.module_render import get_module_for_descriptor
from .utils import MaxScoresCache, get_score

log = logging.getLogger("openedx.grading_policy")


class ProgressSummary(object):
    """
    Wrapper class for the computation of a user's scores across a course.

    Attributes
       chapters: a summary of all sections with problems in the course. It is
       organized as an array of chapters, each containing an array of sections,
       each containing an array of scores. This contains information for graded
       and ungraded problems, and is good for displaying a course summary with
       due dates, etc.

       weighted_scores: a dictionary mapping module locations to weighted Score
       objects.

       locations_to_children: a dictionary mapping module locations to their
       direct descendants.
    """
    def __init__(self, chapters, weighted_scores, locations_to_children):
        self.chapters = chapters
        self.weighted_scores = weighted_scores
        self.locations_to_children = locations_to_children

    def score_for_module(self, location):
        """
        Calculate the aggregate weighted score for any location in the course.
        This method returns a tuple containing (earned_score, possible_score).

        If the location is of 'problem' type, this method will return the
        possible and earned scores for that problem. If the location refers to a
        composite module (a vertical or section ) the scores will be the sums of
        all scored problems that are children of the chosen location.
        """
        if location in self.weighted_scores:
            score = self.weighted_scores[location]
            return score.earned, score.possible
        children = self.locations_to_children[location]
        earned = 0.0
        possible = 0.0
        for child in children:
            child_earned, child_possible = self.score_for_module(child)
            earned += child_earned
            possible += child_possible
        return earned, possible


class SequentialGrading(object):
    """Contains the logic to grade courses by sequentials."""
    PROGRESS_SUMMARY_TEMPLATE = '/grading_policy/templates/summary/sequential.html'

    @staticmethod
    def grade(student, request, course, keep_raw_scores, field_data_cache, scores_client):
        """
        Unwrapped version of "grade"
        This grades a student as quickly as possible. It returns the
        output from the course grader, augmented with the final letter
        grade. The keys in the output are:
        course: a CourseDescriptor
        - grade : A final letter grade.
        - percent : The final percent for the class (rounded up).
        - section_breakdown : A breakdown of each section that makes
          up the grade. (For display)
        - grade_breakdown : A breakdown of the major components that
          make up the final grade. (For display)
        - keep_raw_scores : if True, then value for key 'raw_scores' contains scores
          for every graded module
        More information on the format is in the docstring for CourseGrader.
        """
        with outer_atomic():
            if field_data_cache is None:
                field_data_cache = field_data_cache_for_grading(course, student)
            if scores_client is None:
                scores_client = ScoresClient.from_field_data_cache(field_data_cache)

        # Dict of item_ids -> (earned, possible) point tuples. This *only* grabs
        # scores that were registered with the submissions API, which for the moment
        # means only openassessment (edx-ora2)
        # We need to import this here to avoid a circular dependency of the form:
        # XBlock --> submissions --> Django Rest Framework error strings -->
        # Django translation --> ... --> courseware --> submissions
        from submissions import api as sub_api  # installed from the edx-submissions repository

        with outer_atomic():
            submissions_scores = sub_api.get_scores(
                course.id.to_deprecated_string(),
                anonymous_id_for_user(student, course.id)
            )
            max_scores_cache = MaxScoresCache.create_for_course(course)

            # For the moment, we have to get scorable_locations from field_data_cache
            # and not from scores_client, because scores_client is ignorant of things
            # in the submissions API. As a further refactoring step, submissions should
            # be hidden behind the ScoresClient.
            max_scores_cache.fetch_from_remote(field_data_cache.scorable_locations)

        grading_context = course.grading_context
        raw_scores = []

        totaled_scores = {}
        # This next complicated loop is just to collect the totaled_scores, which is
        # passed to the grader
        for section_format, sections in grading_context['graded_sections'].iteritems():
            format_scores = []
            for section in sections:
                section_descriptor = section['section_descriptor']
                section_name = section_descriptor.display_name_with_default_escaped

                with outer_atomic():
                    # some problems have state that is updated independently of interaction
                    # with the LMS, so they need to always be scored. (E.g. combinedopenended ORA1)
                    # TODO This block is causing extra savepoints to be fired that are empty because no queries are executed
                    # during the loop. When refactoring this code please keep this outer_atomic call in mind and ensure we
                    # are not making unnecessary database queries.
                    should_grade_section = any(
                        descriptor.always_recalculate_grades for descriptor in section['xmoduledescriptors']
                    )

                    # If there are no problems that always have to be regraded, check to
                    # see if any of our locations are in the scores from the submissions
                    # API. If scores exist, we have to calculate grades for this section.
                    if not should_grade_section:
                        should_grade_section = any(
                            descriptor.location.to_deprecated_string() in submissions_scores
                            for descriptor in section['xmoduledescriptors']
                        )

                    if not should_grade_section:
                        should_grade_section = any(
                            descriptor.location in scores_client
                            for descriptor in section['xmoduledescriptors']
                        )

                    # If we haven't seen a single problem in the section, we don't have
                    # to grade it at all! We can assume 0%
                    if should_grade_section:
                        scores = []

                        def create_module(descriptor):
                            '''creates an XModule instance given a descriptor'''
                            # TODO: We need the request to pass into here. If we could forego that, our arguments
                            # would be simpler
                            return get_module_for_descriptor(
                                student, request, descriptor, field_data_cache, course.id, course=course
                            )

                        descendants = yield_dynamic_descriptor_descendants(section_descriptor, student.id, create_module)
                        for module_descriptor in descendants:
                            user_access = has_access(
                                student, 'load', module_descriptor, module_descriptor.location.course_key
                            )
                            if not user_access:
                                continue

                            (correct, total) = get_score(
                                student,
                                module_descriptor,
                                create_module,
                                scores_client,
                                submissions_scores,
                                max_scores_cache,
                            )
                            if correct is None and total is None:
                                continue

                            if settings.GENERATE_PROFILE_SCORES:    # for debugging!
                                if total > 1:
                                    correct = random.randrange(max(total - 2, 1), total + 1)
                                else:
                                    correct = total

                            graded = module_descriptor.graded
                            if not total > 0:
                                # We simply cannot grade a problem that is 12/0, because we might need it as a percentage
                                graded = False

                            scores.append(
                                Score(
                                    correct,
                                    total,
                                    graded,
                                    module_descriptor.display_name_with_default_escaped,
                                    module_descriptor.location
                                )
                            )

                        __, graded_total = graders.aggregate_scores(scores, section_name)
                        if keep_raw_scores:
                            raw_scores += scores
                    else:
                        graded_total = Score(0.0, 1.0, True, section_name, None)

                    #Add the graded total to totaled_scores
                    if graded_total.possible > 0:
                        format_scores.append(graded_total)
                    else:
                        log.info(
                            "Unable to grade a section with a total possible score of zero. " +
                            str(section_descriptor.location)
                        )

            totaled_scores[section_format] = format_scores

        with outer_atomic():
            # Grading policy might be overriden by a CCX, need to reset it
            course.set_grading_policy(course.grading_policy)
            grade_summary = course.grader.grade(totaled_scores, generate_random_scores=settings.GENERATE_PROFILE_SCORES)

            # We round the grade here, to make sure that the grade is an whole percentage and
            # doesn't get displayed differently than it gets grades
            grade_summary['percent'] = round(grade_summary['percent'] * 100 + 0.05) / 100

            letter_grade = grade_for_percentage(course.grade_cutoffs, grade_summary['percent'])
            grade_summary['grade'] = letter_grade
            grade_summary['totaled_scores'] = totaled_scores   # make this available, eg for instructor download & debugging
            if keep_raw_scores:
                # way to get all RAW scores out to instructor
                # so grader can be double-checked
                grade_summary['raw_scores'] = raw_scores

            max_scores_cache.push_to_remote()

        return grade_summary



    @staticmethod
    def grading_context(course):
        """
        This returns a dictionary with keys necessary for quickly grading
        a student. They are used by grades.grade()
        The grading context has two keys:
        graded_sections - This contains the sections that are graded, as
            well as all possible children modules that can affect the
            grading. This allows some sections to be skipped if the student
            hasn't seen any part of it.
            The format is a dictionary keyed by section-type. The values are
            arrays of dictionaries containing
                "section_descriptor" : The section descriptor
                "xmoduledescriptors" : An array of xmoduledescriptors that
                    could possibly be in the section, for any student
        all_descriptors - This contains a list of all xmodules that can
            effect grading a student. This is used to efficiently fetch
            all the xmodule state for a FieldDataCache without walking
            the descriptor tree again.
        """
        # If this descriptor has been bound to a student, return the corresponding
        # XModule. If not, just use the descriptor itself
        try:
            module = getattr(course, '_xmodule', None)
            if not module:
                module = course
        except UndefinedContext:
            module = course

        def possibly_scored(usage_key):
            """Can this XBlock type can have a score or children?"""
            return usage_key.block_type in course.block_types_affecting_grading

        all_descriptors = []
        graded_sections = {}

        def yield_descriptor_descendents(module_descriptor):
            for child in module_descriptor.get_children(usage_key_filter=possibly_scored):
                yield child
                for module_descriptor in yield_descriptor_descendents(child):
                    yield module_descriptor

        for chapter in course.get_children():
            for section in chapter.get_children():
                if section.graded:
                    xmoduledescriptors = list(yield_descriptor_descendents(section))
                    xmoduledescriptors.append(section)

                    # The xmoduledescriptors included here are only the ones that have scores.
                    section_description = {
                        'section_descriptor': section,
                        'xmoduledescriptors': [child for child in xmoduledescriptors if child.has_score]
                    }

                    section_format = section.format if section.format is not None else ''
                    graded_sections[section_format] = graded_sections.get(section_format, []) + [section_description]

                    all_descriptors.extend(xmoduledescriptors)
                    all_descriptors.append(section)

        return {'graded_sections': graded_sections,
                'all_descriptors': all_descriptors, }





# TODO: This method is not very good. It was written in the old course style and
# then converted over and performance is not good. Once the progress page is redesigned
# to not have the progress summary this method should be deleted (so it won't be copied).
def _progress_summary(student, request, course, field_data_cache=None, scores_client=None):
    """
    Unwrapped version of "progress_summary".
    This pulls a summary of all problems in the course.
    Returns
    - courseware_summary is a summary of all sections with problems in the course.
    It is organized as an array of chapters, each containing an array of sections,
    each containing an array of scores. This contains information for graded and
    ungraded problems, and is good for displaying a course summary with due dates,
    etc.
    Arguments:
        student: A User object for the student to grade
        course: A Descriptor containing the course to grade
    If the student does not have access to load the course module, this function
    will return None.
    """
    with outer_atomic():
        if field_data_cache is None:
            field_data_cache = field_data_cache_for_grading(course, student)
        if scores_client is None:
            scores_client = ScoresClient.from_field_data_cache(field_data_cache)

        course_module = get_module_for_descriptor(
            student, request, course, field_data_cache, course.id, course=course
        )
        if not course_module:
            return None

        course_module = getattr(course_module, '_x_module', course_module)

    # We need to import this here to avoid a circular dependency of the form:
    # XBlock --> submissions --> Django Rest Framework error strings -->
    # Django translation --> ... --> courseware --> submissions
    from submissions import api as sub_api  # installed from the edx-submissions repository
    with outer_atomic():
        submissions_scores = sub_api.get_scores(
            course.id.to_deprecated_string(), anonymous_id_for_user(student, course.id)
        )

        max_scores_cache = MaxScoresCache.create_for_course(course)
        # For the moment, we have to get scorable_locations from field_data_cache
        # and not from scores_client, because scores_client is ignorant of things
        # in the submissions API. As a further refactoring step, submissions should
        # be hidden behind the ScoresClient.
        max_scores_cache.fetch_from_remote(field_data_cache.scorable_locations)

    # Check for gated content
    gated_content = gating_api.get_gated_content(course, student)

    chapters = []
    locations_to_children = defaultdict(list)
    locations_to_weighted_scores = {}
    # Don't include chapters that aren't displayable (e.g. due to error)
    for chapter_module in course_module.get_display_items():
        # Skip if the chapter is hidden
        if chapter_module.hide_from_toc:
            continue

        sections = []
        for section_module in chapter_module.get_display_items():
            # Skip if the section is hidden
            with outer_atomic():
                if section_module.hide_from_toc or unicode(section_module.location) in gated_content:
                    continue

                graded = section_module.graded
                scores = []

                module_creator = section_module.xmodule_runtime.get_module

                for module_descriptor in yield_dynamic_descriptor_descendants(
                        section_module, student.id, module_creator
                ):
                    locations_to_children[module_descriptor.parent].append(module_descriptor.location)
                    (correct, total) = get_score(
                        student,
                        module_descriptor,
                        module_creator,
                        scores_client,
                        submissions_scores,
                        max_scores_cache,
                    )
                    if correct is None and total is None:
                        continue

                    weighted_location_score = Score(
                        correct,
                        total,
                        graded,
                        module_descriptor.display_name_with_default_escaped,
                        module_descriptor.location
                    )

                    scores.append(weighted_location_score)
                    locations_to_weighted_scores[module_descriptor.location] = weighted_location_score

                scores.reverse()
                section_total, _ = graders.aggregate_scores(
                    scores, section_module.display_name_with_default_escaped)

                module_format = section_module.format if section_module.format is not None else ''
                sections.append({
                    'display_name': section_module.display_name_with_default_escaped,
                    'url_name': section_module.url_name,
                    'scores': scores,
                    'section_total': section_total,
                    'format': module_format,
                    'due': section_module.due,
                    'graded': graded,
                })

        chapters.append({
            'course': course.display_name_with_default_escaped,
            'display_name': chapter_module.display_name_with_default_escaped,
            'url_name': chapter_module.url_name,
            'sections': sections
        })

    max_scores_cache.push_to_remote()

    return ProgressSummary(chapters, locations_to_weighted_scores, locations_to_children)



