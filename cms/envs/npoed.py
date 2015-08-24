from aws import *


#  ENV_TOKENS file - cms.env.json; AUTH_TOKENS file - cms.auth.json
# Sentry integration
RAVEN_DSN = ENV_TOKENS.get('RAVEN_DSN', None)
if RAVEN_DSN:
    INSTALLED_APPS += ('raven.contrib.django.raven_compat',)
    RAVEN_CONFIG = {
        'dsn': RAVEN_DSN,
    }
