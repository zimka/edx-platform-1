""" receivers of course_published and library_updated events in order to trigger indexing task """
from datetime import datetime
from pytz import UTC
import requests
import os
import logging

from django.dispatch import receiver
from django.conf import settings

from xmodule.modulestore.django import SignalHandler
from contentstore.courseware_index import CoursewareSearchIndexer, LibrarySearchIndexer
from courseware.courses import get_course

log = logging.getLogger('course_signals')

@receiver(SignalHandler.course_published)
def listen_for_course_publish(sender, course_key, **kwargs):  # pylint: disable=unused-argument
    """
    Receives signal and kicks off celery task to update search index
    """
    # import here, because signal is registered at startup, but items in tasks are not yet able to be loaded
    from .tasks import update_search_index
    if CoursewareSearchIndexer.indexing_is_enabled():
        update_search_index.delay(unicode(course_key), datetime.now(UTC).isoformat())


@receiver(SignalHandler.library_updated)
def listen_for_library_update(sender, library_key, **kwargs):  # pylint: disable=unused-argument
    """
    Receives signal and kicks off celery task to update search index
    """
    # import here, because signal is registered at startup, but items in tasks are not yet able to be loaded
    from .tasks import update_library_index
    if LibrarySearchIndexer.indexing_is_enabled():
        update_library_index.delay(unicode(library_key), datetime.now(UTC).isoformat())

@receiver(SignalHandler.course_published)
def push_objects_to_sso(sender, course_key, **kwargs):
    if not hasattr(settings, 'SSO_API_URL'):
        log.error('settings.SSO_API_URL is not defined')
        return

    if not hasattr(settings, 'SSO_API_TOKEN'):
        log.error('SSO_API_TOKEN is not defined')
        return

    url = os.path.join(settings.SSO_API_URL, 'course/')
    headers = {'Authorization': 'Token {}'.format(settings.SSO_API_TOKEN)}
    course = get_course(course_key)
    name = course.name or course_key.run
    start = course.start and datetime.strftime(course.start, '%Y-%m-%dT%H:%M:%SZ') or None
    end = course.end and datetime.strftime(course.end, '%Y-%m-%dT%H:%M:%SZ') or None
    data = {
        'name': name,
        'course_id': course_key.html_id(),
        'start': start,
        'end': end,
        'org': course.org,
        'run': course_key.run,
    }

    r = requests.post(url, headers=headers, data=data)

    if r.ok:
        return r.text
    log.error('API "{}" returned: {}'.format(url, r.status_code))
