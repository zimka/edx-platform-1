"""
Contains the logic for grading by verticals.
"""
# Compute grades using real division, with no integer truncation
from __future__ import division
import logging

from collections import defaultdict, OrderedDict

from grades.scores import possibly_scored
from openedx.core.djangoapps.content.block_structure.api import get_course_in_cache
from xmodule import block_metadata_utils


log = logging.getLogger("openedx.grading_policy")


class VerticalGrading(object):
    """Provides methods to grade courses by verticals."""
    PROGRESS_SUMMARY_TEMPLATE = '/summary/vertical.html'

    @staticmethod
    def grading_context_for_course(course_key):
        """
        Same as grading_context, but takes in a course object.
        """
        course_structure = get_course_in_cache(course_key)
        return VerticalGrading.grading_context(course_structure)

    @staticmethod
    def grading_context(course_structure):
        """
        This returns a dictionary with keys necessary for quickly grading
        a student.

        The grading context has two keys:
        all_graded_verticals_by_type - This contains all verticals that are
            graded, keyed by vertical format (assignment type).

            The values are arrays of dictionaries containing
                "vertical_block" : The vertical block
                "scored_descendants" : An array of usage keys for blocks
                    that could possibly be in the vertical, for any student

        all_graded_blocks - This contains a list of all blocks that can
            affect grading a student. This is used to efficiently fetch
            all the xmodule state for a FieldDataCache without walking
            the descriptor tree again.

        """
        all_graded_blocks = []
        all_graded_verticals_by_type = OrderedDict()

        for chapter_key in course_structure.get_children(course_structure.root_block_usage_key):
            for subsection_key in course_structure.get_children(chapter_key):
                for vertical_key in course_structure.get_children(subsection_key):
                    vertical = course_structure[vertical_key]
                    scored_descendants_of_vertical = []
                    if vertical.graded:
                        for descendant_key in course_structure.post_order_traversal(
                            filter_func=possibly_scored,
                            start_node=vertical_key
                        ):
                            scored_descendants_of_vertical.append(
                                course_structure[descendant_key],
                            )

                        # include only those blocks that have scores, not if they are just a parent
                        vertical_info = {
                            'vertical_block': vertical,
                            'scored_descendants': [
                                child for child in scored_descendants_of_vertical
                                if getattr(child, 'has_score', None)
                            ]
                        }
                        vertical_format = getattr(vertical, 'format', '')
                        if vertical_format not in all_graded_verticals_by_type:
                            all_graded_verticals_by_type[vertical_format] = []
                        all_graded_verticals_by_type[vertical_format].append(vertical_info)
                        all_graded_blocks.extend(scored_descendants_of_vertical)
        return {
            'all_graded_verticals_by_type': all_graded_verticals_by_type,
            'all_graded_blocks': all_graded_blocks,
        }

    @staticmethod
    def graded_scorable_blocks_to_header(course_key):
        """
        Returns an OrderedDict that maps a scorable block's id to its
        headers in the final report.
        """
        scorable_blocks_map = OrderedDict()
        grading_context = VerticalGrading.grading_context_for_course(course_key)
        for assignment_type_name, vertical_infos in grading_context['all_graded_verticals_by_type'].iteritems():
            for vertical_index, vertical_info in enumerate(vertical_infos, start=1):
                for scorable_block in vertical_info['scored_descendants']:
                    header_name = (
                        u"{assignment_type} {vertical_index}: "
                        u"{vertical_name} - {scorable_block_name}"
                    ).format(
                        scorable_block_name=scorable_block.display_name,
                        assignment_type=assignment_type_name,
                        vertical_index=vertical_index,
                        vertical_name=vertical_info['vertical_block'].display_name,
                    )
                    scorable_blocks_map[scorable_block.location] = [header_name + " (Earned)",
                                                                    header_name + " (Possible)"]
        return scorable_blocks_map

    @staticmethod
    def graded_assignments(course_key):
        """
        Returns an OrderedDict that maps an assignment type to a dict of vertical-headers and average-header.
        """
        grading_context = VerticalGrading.grading_context_for_course(course_key)
        graded_assignments_map = OrderedDict()
        for assignment_type_name, vertical_infos in grading_context['all_graded_verticals_by_type'].iteritems():
            graded_verticals_map = OrderedDict()

            for vertical_index, vertical_info in enumerate(vertical_infos, start=1):
                vertical = vertical_info['vertical_block']
                header_name = u"{assignment_type} {vertical_index}: {vertical_name}".format(
                    assignment_type=assignment_type_name,
                    vertical_index=vertical_index,
                    vertical_name=vertical.display_name,
                )
                graded_verticals_map[vertical.location] = header_name

            average_header = u"{assignment_type}".format(assignment_type=assignment_type_name)

            # Use separate vertical and average columns only if
            # there's more than one vertical.
            use_vertical_headers = len(vertical_infos) > 1
            if use_vertical_headers:
                average_header += u" (Avg)"

            graded_assignments_map[assignment_type_name] = {
                'vertical_headers': graded_verticals_map,
                'average_header': average_header,
                'use_vertical_headers': use_vertical_headers
            }
        return graded_assignments_map

    @staticmethod
    def grade_header(graded_assignments):
        grade_header = []
        for assignment_info in graded_assignments.itervalues():
            if assignment_info['use_vertical_headers']:
                grade_header.extend(assignment_info['vertical_headers'].itervalues())
            grade_header.append(assignment_info['average_header'])
        return grade_header

    @staticmethod
    def grade_results(graded_assignments, course_grade):
        grade_result_list = []
        for assignment_type, assignment_info in graded_assignments.iteritems():
            for vertical_location in assignment_info['vertical_headers']:
                try:
                    vertical_grade = VerticalGrading.graded_elements_by_format(course_grade.chapter_grades)[assignment_type][vertical_location]
                except KeyError:
                    grade_result_list.append([u'Not Available'])
                else:
                    if vertical_grade.graded_total.attempted:
                        grade_result_list.append(
                            [vertical_grade.graded_total.earned / vertical_grade.graded_total.possible]
                        )
                    else:
                        grade_result_list.append([u'Not Attempted'])
            if assignment_info['use_vertical_headers']:
                assignment_average = course_grade.grader_result['grade_breakdown'].get(assignment_type, {}).get(
                    'percent'
                )
                grade_result_list.append([assignment_average])
        return grade_result_list

    @staticmethod
    def graded_elements_by_format(chapter_grades):
        """
        Returns grades for the verticals in the course in
        a dict keyed by vertical format types.
        """
        verticals_by_format = defaultdict(OrderedDict)
        for chapter in chapter_grades.itervalues():
            for subsection in chapter['sections'].values():
                for vertical_grade in subsection['verticals']:
                    if vertical_grade.graded:
                        graded_total = vertical_grade.graded_total
                        if graded_total.possible > 0:
                            verticals_by_format[vertical_grade.format][vertical_grade.location] = vertical_grade
        return verticals_by_format

    @staticmethod
    def get_subsection_grades(course_grade, course_structure, chapter_key):
        """
        Returns a list of subsection grades for the given chapter.
        """
        subsections_keys = course_structure.get_children(chapter_key)
        subsections = dict()
        for subsection_key in subsections_keys:
            subsections[subsection_key] = dict()
            subsection = course_structure[subsection_key]
            subsection_vertical_grades = course_grade._get_vertical_grades(course_structure, subsection_key)
            subsections[subsection_key]['verticals'] = subsection_vertical_grades
            subsections[subsection_key]['display_name'] = block_metadata_utils.display_name_with_default_escaped(subsection)
            subsections[subsection_key]['url_name'] = block_metadata_utils.url_name_for_block(subsection)
        return subsections
