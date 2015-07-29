# coding: utf-8
"""
Middleware that checks user standing for the purpose of keeping users with
disabled accounts from accessing the site.
"""
from django.http import HttpResponseForbidden
from django.utils.translation import ugettext as _
from django.conf import settings
from student.models import UserStanding


class UserStandingMiddleware(object):
    """
    Checks a user's standing on request. Returns a 403 if the user's
    status is 'disabled'.
    """
    def process_request(self, request):
        user = request.user
        try:
            user_account = UserStanding.objects.get(user=user.id)
            # because user is a unique field in UserStanding, there will either be
            # one or zero user_accounts associated with a UserStanding
        except UserStanding.DoesNotExist:
            pass
        else:
            if user_account.account_status == UserStanding.ACCOUNT_DISABLED:
                msg = _(
                    'Your account has been disabled. If you believe '
                    'this was done in error, please contact us at '
                    '{support_email}'
                ).format(
                    support_email=u'<a href="mailto:{address}?subject={subject_line}">{address}</a>'.format(
                        address=settings.DEFAULT_FEEDBACK_EMAIL,
                        subject_line=_('Disabled Account'),
                    ),
                )
                return HttpResponseForbidden(msg)


from django.http import HttpResponse


class UserIsStaff(object):
    def process_request(self, request):
        user = request.user
        if user.is_authenticated() and not user.is_staff:
            return HttpResponse(u'У вас нет прав на создание курса. Пожалуйста, обратитесь к администратору '
                                u'community.npoed.ru для предоставления роли "автор курса"')
        else:
            return


from django.http import HttpResponseRedirect
from django.conf import settings
from re import compile

EXEMPT_URLS = [compile(settings.LOGIN_URL.lstrip('/'))]
if hasattr(settings, 'LOGIN_EXEMPT_URLS'):
    EXEMPT_URLS += [compile(expr) for expr in settings.LOGIN_EXEMPT_URLS]

class LoginRequiredMiddleware:
    """
    Middleware that requires a user to be authenticated to view any page other
    than LOGIN_URL. Exemptions to this requirement can optionally be specified
    in settings via a list of regular expressions in LOGIN_EXEMPT_URLS (which
    you can copy from your urls.py).
    Requires authentication middleware and template context processors to be
    loaded. You'll get an error if they aren't.
    """
    def process_request(self, request):
        assert hasattr(request, 'user'), "The Login Required middleware\
 requires authentication middleware to be installed. Edit your\
 MIDDLEWARE_CLASSES setting to insert\
 'django.contrib.auth.middleware.AuthenticationMiddleware'. If that doesn't\
 work, ensure your TEMPLATE_CONTEXT_PROCESSORS setting includes\
 'django.core.context_processors.auth'."
        if not request.user.is_authenticated():
            path = request.path_info.lstrip('/')
            accepted = ['api/studio/v0/course_create/create', 'api/studio/v0/course_create/add_author', 'api/studio/v0/course_create/check_user_access', 'auth/login/NPOED/', 'user_api/v1/account/login_session/', 'jsi18n/', 'auth/complete/NPOED/', 'admin/']
            if not any(m.match(path) for m in EXEMPT_URLS) and path not in accepted:
                print(path)
                print(accepted)
                print('\n\n\n')
                return HttpResponseRedirect('http://courses.npoed.ru/auth/login/NPOED/?auth_entry=login')
    
