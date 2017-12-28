from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.template.loader import render_to_string
from opaque_keys.edx.keys import CourseKey, UsageKey
from util.json_request import JsonResponse
from web_fragments.fragment import Fragment
from xmodule.modulestore.django import modulestore

from lms.djangoapps.courseware import access
from lms.djangoapps.courseware.courses import get_course_with_access
from lms.djangoapps.instructor.views.api import require_level
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from .plugins import SuspiciousMonitorTab

from .utils import get_sequential_base_url
from .models import SuspiciousExamAttempt


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
        proctored_attempts_info = []
        non_proctored_attempts_info = []

        for att in attempts:
            info = att.info()
            block_id = att.exam_location
            block_location = UsageKey.from_string(block_id)
            url_base = get_sequential_base_url(block_location)
            info["url"] = url_base
            if att.is_proctored:
                proctored_attempts_info.append(info)
            else:
                non_proctored_attempts_info.append(info)

        proctored_attempts_info = sorted(proctored_attempts_info, key=lambda x: x["datetime"])[::-1]
        non_proctored_attempts_info = sorted(non_proctored_attempts_info, key=lambda x: x["datetime"])[::-1]

        context = {
            "proctored_attempts": proctored_attempts_info,
            "non_proctored_attempts": non_proctored_attempts_info,
            "delete_url": reverse('delete_suspicious_attempt', kwargs={'course_id':course_id})
        }
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

@require_POST
@require_level('staff')
@ensure_csrf_cookie
def delete_suspicious_attempt(request, course_id):
    """
    Allows instructor to delete not-really-suspicious attempt from course tab
    """
    try:
        attempt_pk = _get_attempt_pk(request.POST.dict())
        attempt = SuspiciousExamAttempt.objects.get(pk=attempt_pk)
    except SuspiciousExamAttempt.DoesNotExist:
        return HttpResponseBadRequest()
    if attempt.course_id != course_id:
        return HttpResponseBadRequest()
    attempt.hide()
    redirect_url = reverse('suspicious_monitor_view', kwargs={"course_id": course_id})
    return HttpResponseRedirect(redirect_url)


# TODO: we use hack to get pk of deleted attempt.
# Once we decide to add any js it should be replaced
def _get_attempt_pk(data):
    """
    Returns primary key of suspicious attempt from form data
    """
    PREFIX = "delete_attempt_"
    keys = [x for x in data.keys() if PREFIX in x]
    if len(keys) != 1:
        return -1
    key = keys[0]
    return int(key.split(PREFIX)[-1])
