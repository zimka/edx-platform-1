from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from openedx.core.djangoapps.course_groups.cohorts import get_course_cohorts, is_course_cohorted


def _section_change_due(course, access):
    """Provide data for change due instructor dashboard section"""
    course_key = course.id
    cohorts = []
    if is_course_cohorted(course_key):
        cohorts = get_course_cohorts(course)
    section_data = {
        'section_key': 'change_due',
        'section_display_name': _('Change due'),
        'access': access,
        'course_id': unicode(course_key),
        'change_due_submit_url': reverse('change_due_submit', kwargs={'course_id': unicode(course_key)}),
        'change_due_tasks_url': reverse('change_due_tasks', kwargs={'course_id': unicode(course_key)}),
        'cohorts': cohorts,
        'changed_due_turned_on':settings.FEATURES.get('INDIVIDUAL_DUE_DATES'),

    }
    return section_data
