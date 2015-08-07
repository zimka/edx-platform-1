from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from util.json_request import JsonResponse

from opaque_keys.edx.keys import CourseKey

from xmodule.modulestore.django import modulestore
from xmodule.course_module import CourseFields
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError

from contentstore.views.course import create_new_course_in_store
from contentstore.utils import reverse_course_url
import logging
log = logging.getLogger(__name__)


def create_course(course_details):
    response_data = {}
    user_email = course_details.get('user_email')
    try:
        user = User.objects.get(email=user_email)
    except ObjectDoesNotExist:
        error = "User with email {} not found".format(user_email)
        return send_error(error)
    # TODO: rewrite to check course author access
    if not user.is_staff:
        error = "No course author access for user {}".format(user_email)
        return send_error(error)
    org = course_details.get('org')
    course = course_details.get('course_number')
    run = course_details.get('course_run')
    if None in [org, course, run]:
        error = "You must specify org, course_number and course_run"
        return send_error(error)
    try:
        display_name = course_details.get('course_name')
        # force the start date for reruns and allow us to override start via the client
        start = CourseFields.start.default
        fields = {'start': start}
        if display_name is not None:
            fields['display_name'] = display_name

        # Set a unique wiki_slug for newly created courses. To maintain active wiki_slugs for
        # existing xml courses this cannot be changed in CourseDescriptor.
        # # TODO get rid of defining wiki slug in this org/course/run specific way and reconcile
        # w/ xmodule.course_module.CourseDescriptor.__init__
        wiki_slug = u"{0}.{1}.{2}".format(org, course, run)
        definition_data = {'wiki_slug': wiki_slug}
        fields.update(definition_data)

        _create_new_course(user, org, course, run, fields)
        message = "Course with id {0}/{1}/{2} successfully created!".format(org, course, run)
        log.info(message)
        response_data['message'] = message
        return response_data

    except DuplicateCourseError:
        error = "Course with parameters {0}/{1}/{2} already exists".format(org, course, run)
        return send_error(error)


def _create_new_course(user, org, number, run, fields):
    """
    Create a new course.
    Returns the URL for the course overview page.
    Raises DuplicateCourseError if the course already exists
    """
    store_for_new_course = modulestore().default_modulestore.get_modulestore_type()
    new_course = create_new_course_in_store(store_for_new_course, user, org, number, run, fields)
    return JsonResponse({
        'url': reverse_course_url('course_handler', new_course.id),
        'course_key': unicode(new_course.id),
    })


def delete_course(course_details):
    response_data = {}
    user_email = course_details.get('user_email')
    try:
        user = User.objects.get(email=user_email)
    except ObjectDoesNotExist:
        error = "User with email {} not found".format(user_email)
        return send_error(error)
    # TODO: rewrite to check course author access
    if not user.is_staff:
        error = "No course author access for user {}".format(user_email)
        return send_error(error)
    org = course_details.get('org')
    course = course_details.get('course_number')
    run = course_details.get('course_run')
    if None in [org, course, run]:
        error = "You must specify org, course_number and course_run"
        return send_error(error)
    try:
        course_key = CourseKey.from_string('{0}/{1}/{2}'.format(org, course, run))
        course_module = modulestore().get_course(course_key)
        if course_module is None:
            error = "Course with id {0}/{1}/{2} not found".format(org, course, run)
            return send_error(error)
        course_module.course_is_hidden_in_lms = True
        modulestore().update_item(course_module, user.id)
        message = "Course with id {0}/{1}/{2} now is accessible only by direct link".format(org, course, run)
        log.info(message)
        response_data['message'] = message
        return response_data
    except ItemNotFoundError:
        error = "Course with id {0}/{1}/{2} not found".format(org, course, run)
        return send_error(error)


def send_error(error):
    response_data = {}
    log.warning(error)
    response_data['error'] = error
    return response_data
