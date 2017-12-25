from django.template.loader import render_to_string
from web_fragments.fragment import Fragment
from opaque_keys.edx.keys import CourseKey

from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from lms.djangoapps.courseware.views.views import modulestore, has_access, setup_masquerade
from lms.djangoapps.courseware.courses import get_course_with_access
from lms.djangoapps.npoed_session_monitor.models import SuspiciousExamAttempt
from util.json_request import JsonResponse

from .plugins import SuspiciousMonitorTab


def suspicious_monitor_view(request, course_id):
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)

    if request.is_ajax():
        return JsonResponse({"message": "OK"})
    else:
        course_id = unicode(course.id)
        tab_view = SuspiciousMonitorFragmentView()
        return tab_view.get(request, course_id=course_id)


class SuspiciousMonitorFragmentView(EdxFragmentView):
    def render_to_fragment(self, request, course_id=None, *args, **kwargs):
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
        attempts = SuspiciousExamAttempt.get_course_attempts(course_id)
        context = {"attempts": [x.to_json() for x in attempts]}
        return context


def _create_context(request, course_id=None, course=None, **kwargs):

    tab = SuspiciousMonitorTab({})
    if not course:
        course = modulestore().get_course(CourseKey.from_string(course_id))

    staff_access = has_access(request.user, 'staff', course)
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