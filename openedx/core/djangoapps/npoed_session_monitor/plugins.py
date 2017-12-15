from django.utils.translation import ugettext_noop
from django.conf import settings

from lms.djangoapps.courseware import tabs, access
from xmodule.tabs import TabFragmentViewMixin


class SuspiciousMonitorTab(TabFragmentViewMixin, tabs.EnrolledTab):
    """
    New Tab where suspicious sessions are shown.
    Tab is visible for instructors only
    """
    type = "suspicious_monitor"
    title = ugettext_noop("Suspicious Monitor")
    view_name = "openedx.core.djangoapps.npoed_session_monitor.views.suspicious_monitor_view"
    fragment_view_name = "openedx.core.djangoapps.npoed_session_monitor.views.SucpiciousMonitorFragmentView"
    priority = None
    is_hideable = False
    is_default = False
    body_class = None
    online_help_token = None
    is_dynamic = True
    course_staff_only = True

    @classmethod
    def is_enabled(cls, course, user=None):
        return settings.FEATURES.get("ENABLE_SUSPICIOUS_MONITOR", False) and \
               bool(user and access.has_access(user, "staff", course, course.id))
