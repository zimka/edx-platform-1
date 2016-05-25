from aws import *


#  ENV_TOKENS file - lms.env.json; AUTH_TOKENS file - lms.auth.json
# Sentry integration
RAVEN_DSN = ENV_TOKENS.get('RAVEN_DSN', None)
if RAVEN_DSN:
    INSTALLED_APPS += ('raven.contrib.django.raven_compat',)
    RAVEN_CONFIG = {
        'dsn': RAVEN_DSN,
    }

SSO_NPOED_URL = ENV_TOKENS.get('SSO_NPOED_URL').rstrip('/') #'http://sso.rnoep.raccoongang.com'

SSO_API_URL = "%s/api-edx/" % SSO_NPOED_URL  #'http://sso.rnoep.raccoongang.com/api-edx/'
SSO_API_TOKEN = AUTH_TOKENS.get('SSO_API_TOKEN') #'b4c2b895087d457b86fc9096f344a687947b70fb'


SOCIAL_AUTH_EXCLUDE_URL_PATTERN = r'^/admin'
SOCIAL_AUTH_LOGOUT_URL = "%s/logout/" % SSO_NPOED_URL #'http://sso.rnoep.raccoongang.com/logout/'
SOCIAL_AUTH_RAISE_EXCEPTIONS = True

MIDDLEWARE_CLASSES += ('sso_edx_npoed.middleware.PLPRedirection',
                       'sso_edx_npoed.middleware.SeamlessAuthorization',
                       'sso_edx_npoed.middleware.CheckHonorAccepted')

PLP_URL = ENV_TOKENS.get('PLP_URL').rstrip('/')

# We should login always with npoed-sso
# from sso_edx_npoed.backends.npoed import NpoedBackend
# NpoedBackend.name
SSO_NPOED_BACKEND_NAME = 'sso_npoed-oauth2'
LOGIN_URL = '/auth/login/%s/' % SSO_NPOED_BACKEND_NAME

# Add extra dir for mako templates finder
# '/edx/app/edxapp/venvs/edxapp/src/npoed-sso-edx-client/sso_edx_npoed/templates')
NPOED_MAKO_TEMPLATES = ENV_TOKENS.get('NPOED_MAKO_TEMPLATES', [])

#TEMPLATE_DIRS.insert(0, '/edx/app/edxapp/venvs/edxapp/src/npoed-sso-edx-client/sso_edx_npoed')
MAKO_TEMPLATES['main'] = NPOED_MAKO_TEMPLATES + MAKO_TEMPLATES['main']

#OAUTH_OIDC_ISSUER = "https://rnoep.raccoongang.com/oauth2"

EVMS_URL = ENV_TOKENS.get('EVMS_URL')
EVMS_API_KEY = AUTH_TOKENS.get('EVMS_API_KEY')
EXAMUS_PROCTORING_AUTH = AUTH_TOKENS.get('EXAMUS_PROCTORING_AUTH', {})

ORA2_FILEUPLOAD_BACKEND = ENV_TOKENS.get('ORA2_FILEUPLOAD_BACKEND', 'filesystem')
ORA2_FILEUPLOAD_ROOT = ENV_TOKENS.get('ORA2_FILEUPLOAD_ROOT', '/edx/var/edxapp/ora2')
ORA2_FILEUPLOAD_CACHE_NAME = ENV_TOKENS.get('ORA2_FILEUPLOAD_CACHE_NAME', 'ora2_cache')

ROOT_URLCONF = 'sso_edx_npoed.lms_urls'

PLP_API_KEY = AUTH_TOKENS.get('PLP_API_KEY')
