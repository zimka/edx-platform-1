"""
Contains the logic for grading by verticals.
"""
# Compute grades using real division, with no integer truncation
from __future__ import division
import random
import logging
from collections import namedtuple, defaultdict

from django.conf import settings
from courseware.model_data import ScoresClient
from util.db import outer_atomic
from student.models import anonymous_id_for_user
from xmodule import graders, block_metadata_utils
from xmodule.modulestore.django import modulestore
from openedx.core.lib.gating import api as gating_api
from utils import MaxScoresCache, grade_for_percentage, get_score, possibly_scored
from course_blocks.api import get_course_blocks
from submissions import api as sub_api  # installed from the edx-submissions repository

log = logging.getLogger("openedx.grading_policy")


# This is a tuple for holding scores from sections.
# Section indicates the name of the section
WeightedScore = namedtuple("WeightedScore", "earned possible graded section module_id weight")


def aggregate_section_scores(scores, section_name="summary", weight=1.0, module_id=None):
    """
    Aggregates all passed scores.
    scores: A list of WeightedScore objects
    returns: A tuple (all_total, graded_total).
        all_total: A WeightedScore representing the total score summed over all input scores
        graded_total: A WeightedScore representing the score summed over all graded input scores
    """
    total_correct_graded = sum(score.earned for score in scores if score.graded)
    total_possible_graded = sum(score.possible for score in scores if score.graded)

    total_correct = sum(score.earned for score in scores)
    total_possible = sum(score.possible for score in scores)

    # regardless of whether or not it is graded
    all_total = WeightedScore(
        total_correct,
        total_possible,
        False,
        section_name,
        module_id,
        weight
    )
    # selecting only graded things
    graded_total = WeightedScore(
        total_correct_graded,
        total_possible_graded,
        True,
        section_name,
        module_id,
        weight
    )

    return all_total, graded_total


class VerticalGrading(object):
    """Provides methods to grade courses by verticals."""
    PROGRESS_SUMMARY_TEMPLATE = '/grading_policy/templates/summary/vertical.html'

    @staticmethod
    def grading_context(course_structure, grading_type='vertical'):
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

        all_graded_blocks = []
        all_graded_sections = defaultdict(list)

        for chapter_key in course_structure.get_children(course_structure.root_block_usage_key):
            for section_key in course_structure.get_children(chapter_key):
                for vertical_key in course_structure.get_children(section_key):
                    vertical = course_structure[vertical_key]
                    scored_descendants_of_vertical = [vertical]
                    if vertical.graded:
                        for descendant_key in course_structure.post_order_traversal(
                                filter_func=possibly_scored,
                                start_node=vertical_key,
                        ):
                            scored_descendants_of_vertical.append(
                                course_structure[descendant_key],
                            )

                        # include only those blocks that have scores, not if they are just a parent
                        vertical_info = {
                            'section_block': vertical,
                            'section_descriptor': vertical,
                            'scored_descendants': [
                                child for child in scored_descendants_of_vertical
                                if getattr(child, 'has_score', None)
                            ]
                        }
                        section_format = getattr(vertical, 'format', '')
                        all_graded_sections[section_format].append(vertical_info)
                        all_graded_blocks.extend(scored_descendants_of_vertical)

        return {
            'all_graded_sections': all_graded_sections,
            'all_graded_blocks': all_graded_blocks,
        }

    
    @staticmethod
    def grade(student, course, keep_raw_scores=False):
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
        scorable_locations = [block.location for block in [b for b in grading_context_result['all_graded_blocks'] if b is not None]]

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

        totaled_scores, raw_scores = calculate_totaled_scores(
            student, grading_context_result, max_scores_cache, submissions_scores, scores_client, keep_raw_scores
        )

        with outer_atomic():
            # Grading policy might be overriden by a CCX, need to reset it
            course.set_grading_policy(course.grading_policy)
            totaled_scores_ids = []
            for values_list in totaled_scores.values():
                totaled_scores_ids = totaled_scores_ids + [unicode(ws.module_id) for ws in values_list]
            unpublished_graded_verticals = {}
            all_verticals_in_course = modulestore().get_items(course.id, qualifiers = {'category': 'vertical'})
            for vertical in all_verticals_in_course:
                if vertical.graded and unicode(vertical.scope_ids.usage_id) not in totaled_scores_ids:
                    if vertical.format in unpublished_graded_verticals:
                        unpublished_graded_verticals[vertical.format].append(vertical.weight)
                    else:
                        unpublished_graded_verticals[vertical.format] = [vertical.weight]
            grade_summary = course.grader.grade(totaled_scores, generate_random_scores=settings.GENERATE_PROFILE_SCORES, unpublished_graded_verticals=unpublished_graded_verticals)

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

    @staticmethod
    def progress_summary(student, course, grading_type='vertical'):
        """
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
        course_structure = get_course_blocks(student, course.location)
        if not len(course_structure):
            return None
        scorable_locations = [block_key for block_key in course_structure if possibly_scored(block_key)]

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
        if course_structure.get_children(course_structure.root_block_usage_key):
            blocks_stack = [course_structure.root_block_usage_key]
        else:
            blocks_stack = []
        blocks_dict = {}

        while blocks_stack:
            key = blocks_stack.pop()
            curr_block = course_structure[key]
            with outer_atomic():
                children = course_structure.get_children(key) if curr_block.category != grading_type else []
                block = {
                    'display_name': block_metadata_utils.display_name_with_default_escaped(curr_block),
                    'block_type': curr_block.category,
                    'url_name': block_metadata_utils.url_name_for_block(curr_block),
                    'children': [unicode(child) for child in children],
                }

                if curr_block.category == grading_type:
                    graded = curr_block.graded
                    scores = []

                    for descendant_key in course_structure.post_order_traversal(
                            filter_func=possibly_scored,
                            start_node=curr_block.location
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

                        weighted_location_score = graders.Score(
                            correct,
                            total,
                            graded,
                            block_metadata_utils.display_name_with_default_escaped(descendant),
                            descendant.location
                        )

                        scores.append(weighted_location_score)

                    scores.reverse()
                    total, _ = aggregate_section_scores(scores, block_metadata_utils.display_name_with_default_escaped(curr_block))

                    module_format = curr_block.format if curr_block.format is not None else ''
                    block.update({
                        'scores': scores,
                        'total': total,
                        'format': module_format,
                        'due': curr_block.due,
                        'graded': graded,
                    })

                blocks_dict[unicode(key)] = block
                # Add this blocks children to the stack so that we can traverse them as well.
                blocks_stack.extend(children)

        max_scores_cache.push_to_remote()
        return {
            'root': unicode(course.scope_ids.usage_id),
            'blocks': blocks_dict,
        }

def calculate_totaled_scores(
        student,
        grading_context_result,
        max_scores_cache,
        submissions_scores,
        scores_client,
        keep_raw_scores,
):
    if True:
        """
        Returns the totaled scores, which can be passed to the grader.
        """
        raw_scores = []
        totaled_scores = {}
        for section_format, sections in grading_context_result['all_graded_sections'].iteritems():
            format_scores = []
            for section_info in sections:
                section = section_info['section_block']
                section_descriptor = section_info['section_descriptor']
                try:
                    section_name = block_metadata_utils.display_name_with_default(section)
                except:
                    section_name = ""

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
                                graders.Score(
                                    correct,
                                    total,
                                    graded,
                                    block_metadata_utils.display_name_with_default_escaped(descendant),
                                    descendant.location
                                )
                            )

                        __, graded_total = aggregate_section_scores(
                            scores, section_name, getattr(section_descriptor, 'weight', 1.0), section.location
                        )
                        if keep_raw_scores:
                            raw_scores += scores
                    else:
                        graded_total = WeightedScore(
                            0.0, 1.0, True, section_name, section.location, getattr(section_descriptor, 'weight', 1.0)
                        )

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

