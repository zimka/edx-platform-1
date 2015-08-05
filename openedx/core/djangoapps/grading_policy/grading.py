from courseware.model_data import ScoresClient
from courseware.grades import (
    MaxScoresCache, field_data_cache_for_grading, manual_transaction, get_score,
)
from courseware.module_render import get_module_for_descriptor
from util.module_utils import yield_dynamic_descriptor_descendants
from student.models import anonymous_id_for_user
from xmodule import graders
from xmodule.graders import Score
from xmodule.exceptions import UndefinedContext
from submissions import api as sub_api  # installed from the edx-submissions repository


class CourseGrading(object):
    """Base class, that provides methods to grade courses."""
    GRADING_TYPE = None

    @classmethod
    def progress_summary(cls, *args, **kwargs):
        """Wraps "_progress_summary" and passes GRADING_TYPE."""
        return _progress_summary(cls.GRADING_TYPE, *args, **kwargs)

    @classmethod
    def grading_context(cls, *args, **kwargs):
        """Wraps "_grading_context" and passes GRADING_TYPE."""
        return _grading_context(cls.GRADING_TYPE, *args, **kwargs)


class VerticalGrading(CourseGrading):
    """Provides methods to grade courses by verticals."""
    GRADING_TYPE = 'vertical'


class SequentialGrading(CourseGrading):
    """Provides methods to grade courses by sequentials."""
    GRADING_TYPE = 'sequential'


def _progress_summary(grading_type, student, request, course, field_data_cache=None, scores_client=None):
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

    with manual_transaction():
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

    submissions_scores = sub_api.get_scores(
        course.id.to_deprecated_string(), anonymous_id_for_user(student, course.id)
    )
    max_scores_cache = MaxScoresCache.create_for_course(course)
    # For the moment, we have to get scorable_locations from field_data_cache
    # and not from scores_client, because scores_client is ignorant of things
    # in the submissions API. As a further refactoring step, submissions should
    # be hidden behind the ScoresClient.
    max_scores_cache.fetch_from_remote(field_data_cache.scorable_locations)

    blocks_stack = [course_module]
    blocks_dict = {}

    while blocks_stack:
        curr_block = blocks_stack.pop()
        with manual_transaction():
            # Skip if the block is hidden
            if curr_block.hide_from_toc:
                continue

            key = unicode(curr_block.scope_ids.usage_id)
            children = curr_block.get_display_items() if curr_block.category != grading_type else []
            block = {
                'display_name': curr_block.display_name_with_default,
                'block_type': curr_block.category,
                'url_name': curr_block.url_name,
                'children': [unicode(child.scope_ids.usage_id) for child in children],
            }

            if curr_block.category == grading_type:
                graded = curr_block.graded
                scores = []

                module_creator = curr_block.xmodule_runtime.get_module
                for module_descriptor in yield_dynamic_descriptor_descendants(
                        curr_block, student.id, module_creator
                ):
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

                    scores.append(
                        Score(
                            correct,
                            total,
                            graded,
                            module_descriptor.display_name_with_default,
                            module_descriptor.location
                        )
                    )

                scores.reverse()
                total, _ = graders.aggregate_scores(scores, curr_block.display_name_with_default)

                module_format = curr_block.format if curr_block.format is not None else ''
                block.update({
                    'scores': scores,
                    'total': total,
                    'format': module_format,
                    'due': curr_block.due,
                    'graded': graded,
                })

            blocks_dict[key] = block
            # Add this blocks children to the stack so that we can traverse them as well.
            blocks_stack.extend(children)

    max_scores_cache.push_to_remote()

    return {
        'root': unicode(course.scope_ids.usage_id),
        'blocks': blocks_dict,
    }


def _grading_context(grading_type, course):
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

    blocks_stack = [course]

    while blocks_stack:
        curr_block = blocks_stack.pop()
        if curr_block.category == grading_type and curr_block.graded:
            xmoduledescriptors = list(yield_descriptor_descendents(curr_block))
            xmoduledescriptors.append(curr_block)

            # The xmoduledescriptors included here are only the ones that have scores.
            block_description = {
                'section_descriptor': curr_block,
                'xmoduledescriptors': [child for child in xmoduledescriptors if child.has_score]
            }

            block_format = curr_block.format if curr_block.format is not None else ''
            graded_sections[block_format] = [block_description] + graded_sections.get(block_format, [])

            all_descriptors.extend(xmoduledescriptors)
            all_descriptors.append(curr_block)
        else:
            children = curr_block.get_children() if curr_block.has_children else []
            # Add this blocks children to the stack so that we can traverse them as well.
            blocks_stack.extend(children)
    return {'graded_sections': graded_sections,
            'all_descriptors': all_descriptors, }
