# Compute grades using real division, with no integer truncation
from __future__ import division
import logging

from collections import defaultdict, OrderedDict

from grades.scores import possibly_scored
from openedx.core.djangoapps.content.block_structure.api import get_course_in_cache


log = logging.getLogger("openedx.grading_policy")


class SequentialGrading(object):
    """Provides methods to grade courses by verticals."""
    PROGRESS_SUMMARY_TEMPLATE = '/grading_policy/templates/summary/sequential.html'

    @staticmethod
    def grading_context_for_course(course_key):
        """
        Same as grading_context, but takes in a course object.
        """
        course_structure = get_course_in_cache(course_key)
        return SequentialGrading.grading_context(course_structure)

    @staticmethod
    def grading_context(course_structure):
        """
        This returns a dictionary with keys necessary for quickly grading
        a student.

        The grading context has two keys:
        all_graded_subsections_by_type - This contains all subsections that are
            graded, keyed by subsection format (assignment type).

            The values are arrays of dictionaries containing
                "subsection_block" : The subsection block
                "scored_descendants" : An array of usage keys for blocks
                    that could possibly be in the subsection, for any student

        all_graded_blocks - This contains a list of all blocks that can
            affect grading a student. This is used to efficiently fetch
            all the xmodule state for a FieldDataCache without walking
            the descriptor tree again.

        """
        all_graded_blocks = []
        all_graded_subsections_by_type = OrderedDict()

        for chapter_key in course_structure.get_children(course_structure.root_block_usage_key):
            for subsection_key in course_structure.get_children(chapter_key):
                subsection = course_structure[subsection_key]
                scored_descendants_of_subsection = []
                if subsection.graded:
                    for descendant_key in course_structure.post_order_traversal(
                            filter_func=possibly_scored,
                            start_node=subsection_key,
                    ):
                        scored_descendants_of_subsection.append(
                            course_structure[descendant_key],
                        )

                    # include only those blocks that have scores, not if they are just a parent
                    subsection_info = {
                        'subsection_block': subsection,
                        'scored_descendants': [
                            child for child in scored_descendants_of_subsection
                            if getattr(child, 'has_score', None)
                        ]
                    }
                    subsection_format = getattr(subsection, 'format', '')
                    if subsection_format not in all_graded_subsections_by_type:
                        all_graded_subsections_by_type[subsection_format] = []
                    all_graded_subsections_by_type[subsection_format].append(subsection_info)
                    all_graded_blocks.extend(scored_descendants_of_subsection)

        return {
            'all_graded_subsections_by_type': all_graded_subsections_by_type,
            'all_graded_blocks': all_graded_blocks,
        }

    @staticmethod
    def graded_scorable_blocks_to_header(course_key):
        """
        Returns an OrderedDict that maps a scorable block's id to its
        headers in the final report.
        """
        scorable_blocks_map = OrderedDict()
        grading_context = SequentialGrading.grading_context_for_course(course_key)
        for assignment_type_name, subsection_infos in grading_context['all_graded_subsections_by_type'].iteritems():
            for subsection_index, subsection_info in enumerate(subsection_infos, start=1):
                for scorable_block in subsection_info['scored_descendants']:
                    header_name = (
                        u"{assignment_type} {subsection_index}: "
                        u"{subsection_name} - {scorable_block_name}"
                    ).format(
                        scorable_block_name=scorable_block.display_name,
                        assignment_type=assignment_type_name,
                        subsection_index=subsection_index,
                        subsection_name=subsection_info['subsection_block'].display_name,
                    )
                    scorable_blocks_map[scorable_block.location] = [header_name + " (Earned)",
                                                                    header_name + " (Possible)"]
        return scorable_blocks_map

    @staticmethod
    def graded_assignments(course_key):
        """
        Returns an OrderedDict that maps an assignment type to a dict of subsection-headers and average-header.
        """
        grading_context = SequentialGrading.grading_context_for_course(course_key)
        graded_assignments_map = OrderedDict()
        for assignment_type_name, subsection_infos in grading_context['all_graded_subsections_by_type'].iteritems():
            graded_subsections_map = OrderedDict()

            for subsection_index, subsection_info in enumerate(subsection_infos, start=1):
                subsection = subsection_info['subsection_block']
                header_name = u"{assignment_type} {subsection_index}: {subsection_name}".format(
                    assignment_type=assignment_type_name,
                    subsection_index=subsection_index,
                    subsection_name=subsection.display_name,
                )
                graded_subsections_map[subsection.location] = header_name

            average_header = u"{assignment_type}".format(assignment_type=assignment_type_name)

            # Use separate subsection and average columns only if
            # there's more than one subsection.
            use_subsection_headers = len(subsection_infos) > 1
            if use_subsection_headers:
                average_header += u" (Avg)"

            graded_assignments_map[assignment_type_name] = {
                'subsection_headers': graded_subsections_map,
                'average_header': average_header,
                'use_subsection_headers': use_subsection_headers
            }
        return graded_assignments_map

    @staticmethod
    def grade_header(graded_assignments):
        grade_header = []
        for assignment_info in graded_assignments.itervalues():
            if assignment_info['use_subsection_headers']:
                grade_header.extend(assignment_info['subsection_headers'].itervalues())
            grade_header.append(assignment_info['average_header'])
        return grade_header

    @staticmethod
    def grade_results(graded_assignments, course_grade):
        grade_result_list = []
        for assignment_type, assignment_info in graded_assignments.iteritems():
            for subsection_location in assignment_info['subsection_headers']:
                try:
                    subsection_grade = course_grade.graded_subsections_by_format[assignment_type][subsection_location]
                except KeyError:
                    grade_result_list.append([u'Not Available'])
                else:
                    if subsection_grade.graded_total.attempted:
                        grade_result_list.append(
                            [subsection_grade.graded_total.earned / subsection_grade.graded_total.possible]
                        )
                    else:
                        grade_result_list.append([u'Not Attempted'])
            if assignment_info['use_subsection_headers']:
                assignment_average = course_grade.grader_result['grade_breakdown'].get(assignment_type, {}).get(
                    'percent'
                )
                grade_result_list.append([assignment_average])
        return grade_result_list

    @staticmethod
    def graded_elements_by_format(chapter_grades):
        """
        Returns grades for the subsections in the course in
        a dict keyed by subsection format types.
        """
        subsections_by_format = defaultdict(OrderedDict)
        for chapter in chapter_grades.itervalues():
            for subsection_grade in chapter['sections']:
                if subsection_grade.graded:
                    graded_total = subsection_grade.graded_total
                    if graded_total.possible > 0:
                        subsections_by_format[subsection_grade.format][subsection_grade.location] = subsection_grade
        return subsections_by_format

    @staticmethod
    def get_subsection_grades(course_grade, course_structure, chapter_key):
        """
        Returns a list of subsection grades for the given chapter.
        """
        return course_grade._get_subsection_grades(course_structure, chapter_key)
