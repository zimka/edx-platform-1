from django.utils.translation import ugettext_lazy as _

from .aws import *


SSO_NPOED_URL = ENV_TOKENS.get('SSO_NPOED_URL')
SSO_NPOED_URL = 'https://sso.albania.opro.ciot-env.ru/'
if SSO_NPOED_URL:
    SSO_NPOED_URL = SSO_NPOED_URL.rstrip('/')

SSO_API_URL = "%s/api-edx/" % SSO_NPOED_URL
SSO_API_TOKEN = AUTH_TOKENS.get('SSO_API_TOKEN')


SOCIAL_AUTH_EXCLUDE_URL_PATTERN = r'^/admin'
SOCIAL_AUTH_LOGOUT_URL = "%s/logout/" % SSO_NPOED_URL
SOCIAL_AUTH_RAISE_EXCEPTIONS = True

MIDDLEWARE_CLASSES += (
    'sso_edx_npoed.middleware.PLPRedirection',
    'sso_edx_npoed.middleware.SeamlessAuthorization',
    'sso_edx_npoed.middleware.DemoCourseAutoEnroll',
)

PLP_URL = ENV_TOKENS.get('PLP_URL')
PLP_URL = 'https://albania.opro.ciot-env.ru/'
if PLP_URL:
    PLP_URL = PLP_URL.rstrip('/')

# We should login always with npoed-sso
# from sso_edx_npoed.backends.npoed import NpoedBackend
# NpoedBackend.name
SSO_NPOED_BACKEND_NAME = 'sso_npoed-oauth2'
LOGIN_URL = '/auth/login/%s/' % SSO_NPOED_BACKEND_NAME

# Add extra dir for mako templates finder
# '/edx/app/edxapp/venvs/edxapp/src/npoed-sso-edx-client/sso_edx_npoed/templates'
NPOED_MAKO_TEMPLATES = ENV_TOKENS.get('NPOED_MAKO_TEMPLATES', [])

#TEMPLATE_DIRS.insert(0, '/edx/app/edxapp/venvs/edxapp/src/npoed-sso-edx-client/sso_edx_npoed')
MAKO_TEMPLATES['main'] = NPOED_MAKO_TEMPLATES + MAKO_TEMPLATES['main']

EVMS_URL = ENV_TOKENS.get('EVMS_URL', None)
EVMS_API_KEY = AUTH_TOKENS.get('EVMS_API_KEY', None)

ORA2_FILEUPLOAD_BACKEND = ENV_TOKENS.get('ORA2_FILEUPLOAD_BACKEND', 'filesystem')
ORA2_FILEUPLOAD_ROOT = ENV_TOKENS.get('ORA2_FILEUPLOAD_ROOT', '/edx/var/edxapp/ora2')
ORA2_FILEUPLOAD_CACHE_NAME = ENV_TOKENS.get('ORA2_FILEUPLOAD_CACHE_NAME', 'ora2_cache')

ROOT_URLCONF = 'sso_edx_npoed.lms_urls'

EXAMUS_PROCTORING_AUTH = AUTH_TOKENS.get('EXAMUS_PROCTORING_AUTH', {})

INSTALLED_APPS += ('open_edx_api_extension', 'course_shifts', 'npoed_grading_features',)
FEATURES["ENABLE_COURSE_SHIFTS"] = True
FIELD_OVERRIDE_PROVIDERS += (
    'course_shifts.provider.CourseShiftOverrideProvider',
)
TIME_ZONE_DISPLAYED_FOR_DEADLINES = 'Europe/Moscow'
SSO_API_KEY = 'aac2727346af584cb95d9e6fda6a8f6e985d4dd5'
PLP_API_KEY = '84301f1007ff6cda8d9a2fdf77987830c0fa04dc'
REGISTRATION_EXTRA_FIELDS = {}

SSO_API_TOKEN = '81595d7b3c8b8f84ae6165cdf723b4f28f6068eb'

DEBUG=True



SOCIAL_AUTH_SSO_NPOED_OAUTH2_KEY = '4d042e811860942fa6b7'
SOCIAL_AUTH_SSO_NPOED_OAUTH2_SECRET = 'c58f23ca07eaca73649a736eed5f2a91ba30f8a9'

COURSE_MODE_DEFAULTS = {
    'bulk_sku': None,
    'currency': 'usd',
    'description': None,
    'expiration_datetime': None,
    'min_price': 0,
    'name': _('Honor'),
    'sku': None,
    'slug': 'honor',
    'suggested_prices': '',
}

#EDX_API_KEY = 'EDX_API_KEY'
SILENCED_SYSTEM_CHECKS = ("fields.E300", )
LOCALE_PATHS = (REPO_ROOT + "/npoed_translations", ) + LOCALE_PATHS

FEATURES["ENABLE_GRADING_FEATURES"] = True
FEATURES["ENABLE_PASSING_GRADE"] = True
