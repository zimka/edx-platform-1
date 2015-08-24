"""
A Django settings file for use on AWS while running
database migrations, since we don't want to normally run the
LMS with enough privileges to modify the database schema.
"""

# We intentionally define lots of variables that aren't used, and
# want to import all variables from base settings files
# pylint: disable=wildcard-import, unused-wildcard-import

# Import everything from .aws so that our settings are based on those.
from .aws import *
import os
from django.core.exceptions import ImproperlyConfigured

DB_OVERRIDES = dict(
    PASSWORD=os.environ.get('DB_MIGRATION_PASS', None),
    ENGINE=os.environ.get('DB_MIGRATION_ENGINE', DATABASES['default']['ENGINE']),
    USER=os.environ.get('DB_MIGRATION_USER', DATABASES['default']['USER']),
    NAME=os.environ.get('DB_MIGRATION_NAME', DATABASES['default']['NAME']),
    HOST=os.environ.get('DB_MIGRATION_HOST', DATABASES['default']['HOST']),
    PORT=os.environ.get('DB_MIGRATION_PORT', DATABASES['default']['PORT']),
)

if DB_OVERRIDES['PASSWORD'] is None:
    raise ImproperlyConfigured("No database password was provided for running "
                               "migrations.  This is fatal.")

for override, value in DB_OVERRIDES.iteritems():
    DATABASES['default'][override] = value

# FIXME: пока воткну временно сюда
import datetime

SSO_NPOED_URL = ENV_TOKENS.get('SSO_NPOED_URL') #'http://sso.rnoep.raccoongang.com'

SSO_API_URL = "%s/api-edx/" % SSO_NPOED_URL  #'http://sso.rnoep.raccoongang.com/api-edx/'
SSO_API_TOKEN = AUTH_TOKENS.get('SSO_API_TOKEN') #'b4c2b895087d457b86fc9096f344a687947b70fb'


SOCIAL_AUTH_EXCLUDE_URL_PATTERN = r'^/admin'
SOCIAL_AUTH_LOGOUT_URL = "%s/logout/" % SSO_NPOED_URL #'http://sso.rnoep.raccoongang.com/logout/'
SOCIAL_AUTH_RAISE_EXCEPTIONS = True

MIDDLEWARE_CLASSES += ('sso_edx_npoed.middleware.SeamlessAuthorization', )

# We should login always with npoed-sso. There is specific backend for cms
# from sso_edx_npoed.backends.npoed import NpoedBackendCMS
# NpoedBackendCMS.name
SSO_NPOED_BACKEND_NAME = 'sso_npoed_cms-oauth2'
LOGIN_URL = '/auth/login/%s/' % SSO_NPOED_BACKEND_NAME

# Add extra dir for mako templates finder
# '/edx/app/edxapp/venvs/edxapp/src/npoed-sso-edx-client/sso_edx_npoed/templates')
NPOED_MAKO_TEMPLATES = ENV_TOKENS.get('NPOED_MAKO_TEMPLATES', [])

#TEMPLATE_DIRS.insert(0, '/edx/app/edxapp/venvs/edxapp/src/npoed-sso-edx-client/sso_edx_npoed')
MAKO_TEMPLATES['main'] = NPOED_MAKO_TEMPLATES + MAKO_TEMPLATES['main']


CELERYBEAT_SCHEDULE = {}

##### Third-party auth options ################################################ copied from lms/aws.py
if FEATURES.get('ENABLE_THIRD_PARTY_AUTH'):
    THIRD_PARTY_AUTH_BACKENDS = ENV_TOKENS.get('THIRD_PARTY_AUTH_BACKENDS')

    if THIRD_PARTY_AUTH_BACKENDS:
        AUTHENTICATION_BACKENDS = THIRD_PARTY_AUTH_BACKENDS + list(AUTHENTICATION_BACKENDS)

    # The reduced session expiry time during the third party login pipeline. (Value in seconds)
    SOCIAL_AUTH_PIPELINE_TIMEOUT = ENV_TOKENS.get('SOCIAL_AUTH_PIPELINE_TIMEOUT', 600)

    # third_party_auth config moved to ConfigurationModels. This is for data migration only:
    THIRD_PARTY_AUTH_OLD_CONFIG = AUTH_TOKENS.get('THIRD_PARTY_AUTH', None)

    if ENV_TOKENS.get('THIRD_PARTY_AUTH_SAML_FETCH_PERIOD_HOURS', 24) is not None:
        CELERYBEAT_SCHEDULE['refresh-saml-metadata'] = {
            'task': 'third_party_auth.fetch_saml_metadata',
            'schedule': datetime.timedelta(hours=ENV_TOKENS.get('THIRD_PARTY_AUTH_SAML_FETCH_PERIOD_HOURS', 24)),
        }

#  ENV_TOKENS file - cms.env.json; AUTH_TOKENS file - cms.auth.json
# Sentry integration
RAVEN_DSN = ENV_TOKENS.get('RAVEN_DSN', None)
if RAVEN_DSN:
    INSTALLED_APPS += ('raven.contrib.django.raven_compat',)
    RAVEN_CONFIG = {
        'dsn': RAVEN_DSN,
    }
