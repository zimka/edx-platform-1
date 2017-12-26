from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from django.http import Http404
from web_fragments.fragment import Fragment
from opaque_keys.edx.keys import CourseKey, UsageKey

from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from lms.djangoapps.courseware import access
from xmodule.modulestore.django import modulestore
from lms.djangoapps.courseware.courses import get_course_with_access
from util.json_request import JsonResponse

from lms.djangoapps.npoed_session_monitor.models import SuspiciousExamAttempt
from cms.djangoapps.contentstore.utils import reverse_usage_url
from .plugins import SuspiciousMonitorTab


def suspicious_monitor_view(request, course_id):
    """
    Basic view for fragment, that can process ajax and synchronous requests.
    Non-staff gets 404
    """
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)
    if not bool(access.has_access(request.user, 'staff', course)):
        raise Http404()

    if request.is_ajax():
        # TODO: Do we need ajax?
        return JsonResponse({"message": "OK"})
    else:
        course_id = unicode(course.id)
        tab_view = SuspiciousMonitorFragmentView()
        return tab_view.get(request, course_id=course_id)


class SuspiciousMonitorFragmentView(EdxFragmentView):
    """
    Fragment view. Renders tab content without header, footer and so on.
    """

    def render_to_fragment(self, request, course_id=None, *args, **kwargs):
        """
        Returns fragment with collected data and static
        """
        context = self.get_fragment_context(course_id)
        html = render_to_string('suspicious_monitor/suspicious_monitor_fragment.html', context)

        fragment = Fragment(html)
        self.add_fragment_resource_urls(fragment)
        return fragment

    def render_to_standalone_html(self, request, fragment, course=None, page_context=None, **kwargs):
        """
        Renders this course tab's fragment to HTML for a standalone page.
        """
        if not page_context:
            page_context = _create_context(request, course=course, **kwargs)
        page_context['fragment'] = fragment
        return render_to_string('courseware/tab-view.html', page_context)

    def get_fragment_context(self, course_id):
        """
        Collects specific for tab data: information about suspicious attempts
        """
        attempts = SuspiciousExamAttempt.get_course_attempts(course_id)
        attempts_info = []
        for att in attempts:
            info = att.info()
            attempts_info.append(info)
            block_id = att.exam_location
            block_location = UsageKey.from_string(block_id)
            url_base = get_sequential_base_url(block_location)
            info["url"] = url_base
        context = {"attempts": attempts_info}
        return context


def _create_context(request, course_id=None, course=None, **kwargs):
    """
    Collects non-specific context for rendering tab at standalone html
    """
    tab = SuspiciousMonitorTab({})
    if not course:
        course = modulestore().get_course(CourseKey.from_string(course_id))

    staff_access = access.has_access(request.user, 'staff', course)
    context = {
        'course': course,
        'tab': tab,
        'active_page': tab.get('type', None),
        'staff_access': staff_access,
        'masquerade': None,
        'supports_preview_menu': False,
        'uses_pattern_library': True,
        'disable_courseware_js': True,
    }
    return context


def get_sequential_base_url(usage_key):
    store = modulestore()
    section = store.get_item(usage_key)
    if section.category != 'sequential':
        raise TypeError('Key must be from sequential')
    chapter = section.get_parent()
    return reverse('courseware_section', kwargs={
        'course_id': str(usage_key.course_key),
        'section': section.location.block_id,
        'chapter': chapter.location.block_id
    })

