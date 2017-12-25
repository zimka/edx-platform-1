from django.utils.translation import ugettext_noop
from django.conf import settings

from lms.djangoapps.courseware import tabs, access

from xmodule.tabs import TabFragmentViewMixin


class SuspiciousMonitorTab(TabFragmentViewMixin, tabs.EnrolledTab):

    type = "suspicious_monitor"
    title = ugettext_noop("Suspicious Monitor")
    priority = None
    view_name = "npoed_session_monitor.views.suspicious_monitor_view"
    fragment_view_name = "npoed_session_monitor.views.SucpiciousMonitorFragmentView"
    is_hideable = False#settings.FEATURES.get("ENABLE_SUSPICIOUS_MONITOR", False)
    is_default = False
    body_class = "suspicious_monitor"
    online_help_token = "suspicious_monitor"
    is_dynamic = True

    @classmethod
    def is_enabled(cls, course, user=None):
        return bool(user and access.has_access(user, "staff", course, course.id))










