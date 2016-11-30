from django.conf.urls import patterns, url

urlpatterns = patterns(
    '',
    url(r'^submit/$', 'openedx.core.djangoapps.bulk_change_due_date.views.post_change_due',
        name='change_due_submit'),
    url(r'^tasks/$', 'openedx.core.djangoapps.bulk_change_due_date.views.get_tasks',
        name='change_due_tasks'),
)
