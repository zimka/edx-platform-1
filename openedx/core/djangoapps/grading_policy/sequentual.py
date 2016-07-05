# Compute grades using real division, with no integer truncation
from __future__ import division

import json
import logging
import random
from collections import defaultdict
from functools import partial
from course_blocks.api import get_course_blocks

import dogstats_wrapper as dog_stats_api
from django.conf import settings
from django.core.cache import cache
from django.test.client import RequestFactory
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import BlockUsageLocator
from openedx.core.lib.cache_utils import memoized

from openedx.core.lib.gating import api as gating_api
from courseware import courses
from courseware.access import has_access
from courseware.model_data import FieldDataCache, ScoresClient
from openedx.core.djangoapps.signals.signals import GRADES_UPDATED
from student.models import anonymous_id_for_user
from util.db import outer_atomic
from util.module_utils import yield_dynamic_descriptor_descendants
from xmodule import graders, block_metadata_utils
from xmodule.exceptions import UndefinedContext
from xmodule.graders import Score
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from courseware.models import StudentModule
from courseware.module_render import get_module_for_descriptor
from .utils import MaxScoresCache, get_score, ProgressSummary

log = logging.getLogger("openedx.grading_policy")


class SequentialGrading(object):
    """Contains the logic to grade courses by sequentials."""
    PROGRESS_SUMMARY_TEMPLATE = '/grading_policy/templates/summary/sequential.html'

    @staticmethod
    def grade(student, course, keep_raw_scores):
        """
        Unwrapped version of "grade"

        This grades a student as quickly as possible. It returns the
        output from the course grader, augmented with the final letter
        grade. The keys in the output are:

        - course: a CourseDescriptor
        - keep_raw_scores : if True, then value for key 'raw_scores' contains scores
          for every graded module

        More information on the format is in the docstring for CourseGrader.
        """
        course_structure = get_course_blocks(student, course.location)
        grading_context_result = course.grading.grading_context(course_structure)
        scorable_locations = [block.location for block in grading_context_result['all_graded_blocks']]

        with outer_atomic():
            scores_client = ScoresClient.create_for_locations(course.id, student.id, scorable_locations)

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

            # For the moment, scores_client is ignorant of scorable_locations
            # in the submissions API. As a further refactoring step, submissions should
            # be hidden behind the ScoresClient.
            max_scores_cache.fetch_from_remote(scorable_locations)

        totaled_scores, raw_scores = course.grading.calculate_totaled_scores(
            student, grading_context_result, max_scores_cache, submissions_scores, scores_client, keep_raw_scores
        )

        with outer_atomic():
            # Grading policy might be overriden by a CCX, need to reset it
            course.set_grading_policy(course.grading_policy)
            grade_summary = course.grader.grade(totaled_scores, generate_random_scores=settings.GENERATE_PROFILE_SCORES)

            # We round the grade here, to make sure that the grade is a whole percentage and
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

    def calculate_totaled_scores(
            student,
            grading_context_result,
            max_scores_cache,
            submissions_scores,
            scores_client,
            keep_raw_scores,
    ):
        """
        Returns the totaled scores, which can be passed to the grader.
        """
        raw_scores = []
        totaled_scores = {}
        for section_format, sections in grading_context_result['all_graded_sections'].iteritems():
            format_scores = []
            for section_info in sections:
                section = section_info['section_block']
                section_name = block_metadata_utils.display_name_with_default(section)

                with outer_atomic():
                    # Check to
                    # see if any of our locations are in the scores from the submissions
                    # API. If scores exist, we have to calculate grades for this section.
                    should_grade_section = any(
                        unicode(descendant.location) in submissions_scores
                        for descendant in section_info['scored_descendants']
                    )

                    if not should_grade_section:
                        should_grade_section = any(
                            descendant.location in scores_client
                            for descendant in section_info['scored_descendants']
                        )

                    # If we haven't seen a single problem in the section, we don't have
                    # to grade it at all! We can assume 0%
                    if should_grade_section:
                        scores = []

                        for descendant in section_info['scored_descendants']:

                            (correct, total) = get_score(
                                student,
                                descendant,
                                scores_client,
                                submissions_scores,
                                max_scores_cache,
                            )
                            if correct is None and total is None:
                                continue

                            if settings.GENERATE_PROFILE_SCORES:  # for debugging!
                                if total > 1:
                                    correct = random.randrange(max(total - 2, 1), total + 1)
                                else:
                                    correct = total

                            graded = descendant.graded
                            if not total > 0:
                                # We simply cannot grade a problem that is 12/0, because we might need it as a percentage
                                graded = False

                            scores.append(
                                Score(
                                    correct,
                                    total,
                                    graded,
                                    block_metadata_utils.display_name_with_default_escaped(descendant),
                                    descendant.location
                                )
                            )

                        __, graded_total = graders.aggregate_scores(scores, section_name)
                        if keep_raw_scores:
                            raw_scores += scores
                    else:
                        graded_total = Score(0.0, 1.0, True, section_name, None)

                    # Add the graded total to totaled_scores
                    if graded_total.possible > 0:
                        format_scores.append(graded_total)
                    else:
                        log.info(
                            "Unable to grade a section with a total possible score of zero. " +
                            str(section.location)
                        )

            totaled_scores[section_format] = format_scores

        return totaled_scores, raw_scores

    @staticmethod
    def grading_context(course_structure):
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
                "section_block" : The section block
                "scored_descendant_keys" : An array of usage keys for blocks
                    could possibly be in the section, for any student

        all_graded_blocks - This contains a list of all blocks that can
            affect grading a student. This is used to efficiently fetch
            all the xmodule state for a FieldDataCache without walking
            the descriptor tree again.

        """
        all_graded_blocks = []
        all_graded_sections = defaultdict(list)

        for chapter_key in course_structure.get_children(course_structure.root_block_usage_key):
            for section_key in course_structure.get_children(chapter_key):
                section = course_structure[section_key]
                scored_descendants_of_section = [section]
                if section.graded:
                    for descendant_key in course_structure.post_order_traversal(
                            filter_func=possibly_scored,
                            start_node=section_key,
                    ):
                        scored_descendants_of_section.append(
                            course_structure[descendant_key],
                        )

                    # include only those blocks that have scores, not if they are just a parent
                    section_info = {
                        'section_block': section,
                        'scored_descendants': [
                            child for child in scored_descendants_of_section
                            if getattr(child, 'has_score', None)
                        ]
                    }
                    section_format = getattr(section, 'format', '')
                    all_graded_sections[section_format].append(section_info)
                    all_graded_blocks.extend(scored_descendants_of_section)

        return {
            'all_graded_sections': all_graded_sections,
            'all_graded_blocks': all_graded_blocks,
        }

    @memoized
    def block_types_with_scores(self):
        pass

    def possibly_scored(course, usage_key):
        """
        Returns whether the given block could impact grading (i.e. scored, or has children).
        """
        return usage_key.block_type in course.grading.block_types_with_scores()


    def progress_summary(student, course):
        """
        Unwrapped version of "progress_summary".

        This pulls a summary of all problems in the course.

        Returns
        - courseware_summary is a summary of all sections with problems in the course.
        It is organized as an array of chapters, each containing an array of sections,
        each containing an array of scores. This contains information for graded and
        ungraded problems, and is good for displaying a course summary with due dates,
        etc.
        - None if the student does not have access to load the course module.

        Arguments:
            student: A User object for the student to grade
            course: A Descriptor containing the course to grade

        """
        course_structure = get_course_blocks(student, course.location)
        if not len(course_structure):
            return None
        scorable_locations = [block_key for block_key in course_structure if course.grading.possibly_scored(course, block_key)]

        with outer_atomic():
            scores_client = ScoresClient.create_for_locations(course.id, student.id, scorable_locations)

        # We need to import this here to avoid a circular dependency of the form:
        # XBlock --> submissions --> Django Rest Framework error strings -->
        # Django translation --> ... --> courseware --> submissions
        from submissions import api as sub_api  # installed from the edx-submissions repository
        with outer_atomic():
            submissions_scores = sub_api.get_scores(
                unicode(course.id), anonymous_id_for_user(student, course.id)
            )

            max_scores_cache = MaxScoresCache.create_for_course(course)
            # For the moment, scores_client is ignorant of scorable_locations
            # in the submissions API. As a further refactoring step, submissions should
            # be hidden behind the ScoresClient.
            max_scores_cache.fetch_from_remote(scorable_locations)

        # Check for gated content
        gated_content = gating_api.get_gated_content(course, student)

        chapters = []
        locations_to_weighted_scores = {}

        for chapter_key in course_structure.get_children(course_structure.root_block_usage_key):
            chapter = course_structure[chapter_key]
            sections = []
            for section_key in course_structure.get_children(chapter_key):
                if unicode(section_key) in gated_content:
                    continue

                section = course_structure[section_key]

                graded = getattr(section, 'graded', False)
                scores = []

                for descendant_key in course_structure.post_order_traversal(
                        filter_func=possibly_scored,
                        start_node=section_key,
                ):
                    descendant = course_structure[descendant_key]

                    (correct, total) = get_score(
                        student,
                        descendant,
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
                        block_metadata_utils.display_name_with_default_escaped(descendant),
                        descendant.location
                    )

                    scores.append(weighted_location_score)
                    locations_to_weighted_scores[descendant.location] = weighted_location_score

                escaped_section_name = block_metadata_utils.display_name_with_default_escaped(section)
                section_total, _ = graders.aggregate_scores(scores, escaped_section_name)

                sections.append({
                    'display_name': escaped_section_name,
                    'url_name': block_metadata_utils.url_name_for_block(section),
                    'scores': scores,
                    'section_total': section_total,
                    'format': getattr(section, 'format', ''),
                    'due': getattr(section, 'due', None),
                    'graded': graded,
                })

            chapters.append({
                'course': course.display_name_with_default_escaped,
                'display_name': block_metadata_utils.display_name_with_default_escaped(chapter),
                'url_name': block_metadata_utils.url_name_for_block(chapter),
                'sections': sections
            })

        max_scores_cache.push_to_remote()

        return ProgressSummary(chapters, locations_to_weighted_scores, course_structure.get_children)
