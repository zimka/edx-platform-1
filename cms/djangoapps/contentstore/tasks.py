"""
This file contains celery tasks for contentstore views
"""
from collections import deque
import json
import logging
from celery.task import task
from celery.utils.log import get_task_logger
import pytz
from datetime import datetime
from pytz import UTC

from django.contrib.auth.models import User

from contentstore.courseware_index import CoursewareSearchIndexer, LibrarySearchIndexer, SearchIndexingError
from contentstore.utils import initialize_permissions
from course_action_state.models import CourseRerunState
from opaque_keys.edx.keys import CourseKey
from xmodule.course_module import CourseFields
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError

LOGGER = get_task_logger(__name__)
FULL_COURSE_REINDEX_THRESHOLD = 1


@task()
def rerun_course(source_course_key_string, destination_course_key_string, user_id, fields=None):
    """
    Reruns a course in a new celery task.
    """
    # import here, at top level this import prevents the celery workers from starting up correctly
    from edxval.api import copy_course_videos

    try:
        # deserialize the payload
        source_course_key = CourseKey.from_string(source_course_key_string)
        destination_course_key = CourseKey.from_string(destination_course_key_string)

        date_shift = None
        if fields:
            json_fields = json.loads(fields)
            date_shift = json_fields.pop('shift_date')
            time_shift = json_fields.pop('shift_time')
            if date_shift and time_shift:
                try:
                    date_shift = pytz.utc.localize(datetime.strptime(" ".join([date_shift, time_shift]), "%m/%d/%Y %H:%M"))
                except ValueError:
                    date_shift = None
                    logging.info("Invalid datetime will be ignored")
            elif date_shift:
                try:
                    date_shift = pytz.utc.localize(datetime.strptime(date_shift, "%m/%d/%Y"))
                except ValueError:
                    date_shift = None
                    logging.info("Invalid date will be ignored")

            if date_shift and date_shift < pytz.utc.localize(datetime(1900, 1, 2)):
                date_shift = None
                logging.info("Datetime earlier than 01/02/1900 will be ignored")
            fields = json.dumps(json_fields)
        fields = deserialize_fields(fields) if fields else None

        # use the split modulestore as the store for the rerun course,
        # as the Mongo modulestore doesn't support multiple runs of the same course.
        store = modulestore()
        with store.default_store('split'):
            store.clone_course(source_course_key, destination_course_key, user_id, fields=fields)

        # set initial permissions for the user to access the course.
        initialize_permissions(destination_course_key, User.objects.get(id=user_id))

        if date_shift:
            source_course = store.get_course(source_course_key)
            delta_date = date_shift - source_course.start
            shifting = shift_course(destination_course_key, delta_date, user_id=user_id)
            if not shifting:
                logging.info("Course re-run {} sucessfully shifted".format(str(destination_course_key)))
            else:
                logging.warning("Problems happened during the course {} shifting:'{}'".format(
                    str(destination_course_key),
                    str(shifting))
                )
        # update state: Succeeded
        CourseRerunState.objects.succeeded(course_key=destination_course_key)

        # call edxval to attach videos to the rerun
        copy_course_videos(source_course_key, destination_course_key)

        return "succeeded"

    except DuplicateCourseError as exc:
        # do NOT delete the original course, only update the status
        CourseRerunState.objects.failed(course_key=destination_course_key)
        logging.exception(u'Course Rerun Error')
        return "duplicate course"

    # catch all exceptions so we can update the state and properly cleanup the course.
    except Exception as exc:  # pylint: disable=broad-except
        # update state: Failed
        CourseRerunState.objects.failed(course_key=destination_course_key)
        logging.exception(u'Course Rerun Error')

        try:
            # cleanup any remnants of the course
            modulestore().delete_course(destination_course_key, user_id)
        except ItemNotFoundError:
            # it's possible there was an error even before the course module was created
            pass

        return "exception: " + unicode(exc)


def shift_course(course_key, delta_date, store=None, user_id=0):
    if not store:
        store = modulestore()
    course = store.get_course(course_key)

    queue = deque(course.get_children())
    try:
        while queue:
            item = queue.popleft()
            children = item.get_children()
            if children:
                queue.extend(children)
            if item.start:
                item.start += delta_date
            if item.due:
                item.due += delta_date
            store.update_item(item, user_id)
        attrs = ["start", "enrollment_start", "end", "enrollment_end", "announcement"]
        for a in attrs:
            value = getattr(course, a, False)
            if value:
                value += delta_date
                setattr(course, a, value)
        store.update_item(course, user_id)

        return 0
    except Exception as e:
        return str(e)


def deserialize_fields(json_fields):
    fields = json.loads(json_fields)
    for field_name, value in fields.iteritems():
        fields[field_name] = getattr(CourseFields, field_name).from_json(value)
    return fields


def _parse_time(time_isoformat):
    """ Parses time from iso format """
    return datetime.strptime(
        # remove the +00:00 from the end of the formats generated within the system
        time_isoformat.split('+')[0],
        "%Y-%m-%dT%H:%M:%S.%f"
    ).replace(tzinfo=UTC)


@task()
def update_search_index(course_id, triggered_time_isoformat):
    """ Updates course search index. """
    try:
        course_key = CourseKey.from_string(course_id)
        CoursewareSearchIndexer.index(modulestore(), course_key, triggered_at=(_parse_time(triggered_time_isoformat)))

    except SearchIndexingError as exc:
        LOGGER.error('Search indexing error for complete course %s - %s', course_id, unicode(exc))
    else:
        LOGGER.debug('Search indexing successful for complete course %s', course_id)


@task()
def update_library_index(library_id, triggered_time_isoformat):
    """ Updates course search index. """
    try:
        library_key = CourseKey.from_string(library_id)
        LibrarySearchIndexer.index(modulestore(), library_key, triggered_at=(_parse_time(triggered_time_isoformat)))

    except SearchIndexingError as exc:
        LOGGER.error('Search indexing error for library %s - %s', library_id, unicode(exc))
    else:
        LOGGER.debug('Search indexing successful for library %s', library_id)


@task()
def push_course_update_task(course_key_string, course_subscription_id, course_display_name):
    """
    Sends a push notification for a course update.
    """
    # TODO Use edx-notifications library instead (MA-638).
    from .push_notification import send_push_course_update
    send_push_course_update(course_key_string, course_subscription_id, course_display_name)
