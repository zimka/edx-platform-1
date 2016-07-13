# Compute grades using real division, with no integer truncation
from __future__ import division

import json
import logging
from collections import defaultdict

import dogstats_wrapper as dog_stats_api
from courseware import courses
from django.test.client import RequestFactory
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import BlockUsageLocator
from courseware.model_data import FieldDataCache, ScoresClient
from openedx.core.djangoapps.signals.signals import GRADES_UPDATED
from util.module_utils import yield_dynamic_descriptor_descendants
from openedx.core.djangoapps.content.block_structure.api import get_course_in_cache
from xblock.core import XBlock
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from .models import StudentModule
from .module_render import get_module_for_descriptor


log = logging.getLogger("edx.courseware")


def answer_distributions(course_key):
    """
    Given a course_key, return answer distributions in the form of a dictionary
    mapping:

      (problem url_name, problem display_name, problem_id) -> {dict: answer -> count}

    Answer distributions are found by iterating through all StudentModule
    entries for a given course with type="problem" and a grade that is not null.
    This means that we only count LoncapaProblems that people have submitted.
    Other types of items like ORA or sequences will not be collected. Empty
    Loncapa problem state that gets created from running the progress page is
    also not counted.

    This method accesses the StudentModule table directly instead of using the
    CapaModule abstraction. The main reason for this is so that we can generate
    the report without any side-effects -- we don't have to worry about answer
    distribution potentially causing re-evaluation of the student answer. This
    also allows us to use the read-replica database, which reduces risk of bad
    locking behavior. And quite frankly, it makes this a lot less confusing.

    Also, we're pulling all available records from the database for this course
    rather than crawling through a student's course-tree -- the latter could
    potentially cause us trouble with A/B testing. The distribution report may
    not be aware of problems that are not visible to the user being used to
    generate the report.

    This method will try to use a read-replica database if one is available.
    """
    # dict: { module.module_state_key : (url_name, display_name) }
    state_keys_to_problem_info = {}  # For caching, used by url_and_display_name

    def url_and_display_name(usage_key):
        """
        For a given usage_key, return the problem's url and display_name.
        Handle modulestore access and caching. This method ignores permissions.

        Raises:
            InvalidKeyError: if the usage_key does not parse
            ItemNotFoundError: if there is no content that corresponds
                to this usage_key.
        """
        problem_store = modulestore()
        if usage_key not in state_keys_to_problem_info:
            problem = problem_store.get_item(usage_key)
            problem_info = (problem.url_name, problem.display_name_with_default_escaped)
            state_keys_to_problem_info[usage_key] = problem_info

        return state_keys_to_problem_info[usage_key]

    # Iterate through all problems submitted for this course in no particular
    # order, and build up our answer_counts dict that we will eventually return
    answer_counts = defaultdict(lambda: defaultdict(int))
    for module in StudentModule.all_submitted_problems_read_only(course_key):
        try:
            state_dict = json.loads(module.state) if module.state else {}
            raw_answers = state_dict.get("student_answers", {})
        except ValueError:
            log.error(
                u"Answer Distribution: Could not parse module state for StudentModule id=%s, course=%s",
                module.id,
                course_key,
            )
            continue

        try:
            url, display_name = url_and_display_name(module.module_state_key.map_into_course(course_key))
            # Each problem part has an ID that is derived from the
            # module.module_state_key (with some suffix appended)
            for problem_part_id, raw_answer in raw_answers.items():
                # Convert whatever raw answers we have (numbers, unicode, None, etc.)
                # to be unicode values. Note that if we get a string, it's always
                # unicode and not str -- state comes from the json decoder, and that
                # always returns unicode for strings.
                answer = unicode(raw_answer)
                answer_counts[(url, display_name, problem_part_id)][answer] += 1

        except (ItemNotFoundError, InvalidKeyError):
            msg = (
                "Answer Distribution: Item {} referenced in StudentModule {} " +
                "for user {} in course {} not found; " +
                "This can happen if a student answered a question that " +
                "was later deleted from the course. This answer will be " +
                "omitted from the answer distribution CSV."
            ).format(
                module.module_state_key, module.id, module.student_id, course_key
            )
            log.warning(msg)
            continue

    return answer_counts


def grading_context_for_course(course):
    """
    Same as grading_context, but takes in a course object.
    """
    course_structure = get_course_in_cache(course.id)
    return course.grading.grading_context(course_structure)


def grade(student, course, keep_raw_scores=False):
    """
    Returns the grade of the student.

    Also sends a signal to update the minimum grade requirement status.
    """
    grade_summary = course.grading.grade(student, course, keep_raw_scores)
    responses = GRADES_UPDATED.send_robust(
        sender=None,
        username=student.username,
        grade_summary=grade_summary,
        course_key=course.id,
        deadline=course.end
    )

    for receiver, response in responses:
        log.info('Signal fired when student grade is calculated. Receiver: %s. Response: %s', receiver, response)

    return grade_summary


def progress_summary(student, course):
    """
    Returns progress summary for all chapters in the course.
    """

    progress = course.grading.progress_summary(student, course)
    if progress:
        return progress.chapters
    else:
        return None


def get_weighted_scores(student, course):
    """
    Uses the _progress_summary method to return a ProgressSummary object
    containing details of a students weighted scores for the course.
    """
    return course.grading.progress_summary(student, course)


def iterate_grades_for(course_or_id, students, keep_raw_scores=False):
    """Given a course_id and an iterable of students (User), yield a tuple of:

    (student, gradeset, err_msg) for every student enrolled in the course.

    If an error occurred, gradeset will be an empty dict and err_msg will be an
    exception message. If there was no error, err_msg is an empty string.

    The gradeset is a dictionary with the following fields:

    - grade : A final letter grade.
    - percent : The final percent for the class (rounded up).
    - section_breakdown : A breakdown of each section that makes
        up the grade. (For display)
    - grade_breakdown : A breakdown of the major components that
        make up the final grade. (For display)
    - raw_scores: contains scores for every graded module
    """
    if isinstance(course_or_id, (basestring, CourseKey)):
        course = courses.get_course_by_id(course_or_id)
    else:
        course = course_or_id

    for student in students:
        with dog_stats_api.timer('lms.grades.iterate_grades_for', tags=[u'action:{}'.format(course.id)]):
            try:
                gradeset = grade(student, course, keep_raw_scores)
                yield student, gradeset, ""
            except Exception as exc:  # pylint: disable=broad-except
                # Keep marching on even if this student couldn't be graded for
                # some reason, but log it for future reference.
                log.exception(
                    'Cannot grade student %s (%s) in course %s because of exception: %s',
                    student.username,
                    student.id,
                    course.id,
                    exc.message
                )
                yield student, {}, exc.message


def _get_mock_request(student):
    """
    Make a fake request because grading code expects to be able to look at
    the request. We have to attach the correct user to the request before
    grading that student.
    """
    request = RequestFactory().get('/')
    request.user = student
    return request


def _calculate_score_for_modules(user_id, course, modules):
    """
    Calculates the cumulative score (percent) of the given modules
    """

    # removing branch and version from exam modules locator
    # otherwise student module would not return scores since module usage keys would not match
    modules = [m for m in modules]
    locations = [
        BlockUsageLocator(
            course_key=course.id,
            block_type=module.location.block_type,
            block_id=module.location.block_id
        )
        if isinstance(module.location, BlockUsageLocator) and module.location.version
        else module.location
        for module in modules
    ]

    scores_client = ScoresClient(course.id, user_id)
    scores_client.fetch_scores(locations)

    # Iterate over all of the exam modules to get score percentage of user for each of them
    module_percentages = []
    ignore_categories = ['course', 'chapter', 'sequential', 'vertical', 'randomize', 'library_content']
    for index, module in enumerate(modules):
        if module.category not in ignore_categories and (module.graded or module.has_score):
            module_score = scores_client.get(locations[index])
            if module_score:
                correct = module_score.correct or 0
                total = module_score.total or 1
                module_percentages.append(correct / total)

    return sum(module_percentages) / float(len(module_percentages)) if module_percentages else 0


def get_module_score(user, course, module):
    """
    Collects all children of the given module and calculates the cumulative
    score for this set of modules for the given user.

    Arguments:
        user (User): The user
        course (CourseModule): The course
        module (XBlock): The module

    Returns:
        float: The cumulative score
    """
    def inner_get_module(descriptor):
        """
        Delegate to get_module_for_descriptor
        """
        field_data_cache = FieldDataCache([descriptor], course.id, user)
        return get_module_for_descriptor(
            user,
            _get_mock_request(user),
            descriptor,
            field_data_cache,
            course.id,
            course=course
        )

    modules = yield_dynamic_descriptor_descendants(
        module,
        user.id,
        inner_get_module
    )
    return _calculate_score_for_modules(user.id, course, modules)
