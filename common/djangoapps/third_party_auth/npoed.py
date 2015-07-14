"""
LinkedIn OAuth1 and OAuth2 backend, docs at:
    http://psa.matiasaguirre.net/docs/backends/linkedin.html
"""
from social.backends.oauth import BaseOAuth2


_DEFAULT_ICON_CLASS = 'fa-sign-in'


class BaseProvider(object):
    """Abstract base class for third-party auth providers.

    All providers must subclass BaseProvider -- otherwise, they cannot be put
    in the provider Registry.
    """

    # Class. The provider's backing social.backends.base.BaseAuth child.
    BACKEND_CLASS = None
    # String. Name of the FontAwesome glyph to use for sign in buttons (or the
    # name of a user-supplied custom glyph that is present at runtime).
    ICON_CLASS = _DEFAULT_ICON_CLASS
    # String. User-facing name of the provider. Must be unique across all
    # enabled providers. Will be presented in the UI.
    NAME = None
    # Dict of string -> object. Settings that will be merged into Django's
    # settings instance. In most cases the value will be None, since real
    # values are merged from .json files (foo.auth.json; foo.env.json) onto the
    # settings instance during application initialization.
    SETTINGS = {}

    @classmethod
    def get_authentication_backend(cls):
        """Gets associated Django settings.AUTHENTICATION_BACKEND string."""
        return '%s.%s' % (cls.BACKEND_CLASS.__module__, cls.BACKEND_CLASS.__name__)

    @classmethod
    def get_email(cls, unused_provider_details):
        """Gets user's email address.

        Provider responses can contain arbitrary data. This method can be
        overridden to extract an email address from the provider details
        extracted by the social_details pipeline step.

        Args:
            unused_provider_details: dict of string -> string. Data about the
                user passed back by the provider.

        Returns:
            String or None. The user's email address, if any.
        """
        return None

    @classmethod
    def get_name(cls, unused_provider_details):
        """Gets user's name.

        Provider responses can contain arbitrary data. This method can be
        overridden to extract a full name for a user from the provider details
        extracted by the social_details pipeline step.

        Args:
            unused_provider_details: dict of string -> string. Data about the
                user passed back by the provider.

        Returns:
            String or None. The user's full name, if any.
        """
        return None

    @classmethod
    def get_register_form_data(cls, pipeline_kwargs):
        """Gets dict of data to display on the register form.

        common.djangoapps.student.views.register_user uses this to populate the
        new account creation form with values supplied by the user's chosen
        provider, preventing duplicate data entry.

        Args:
            pipeline_kwargs: dict of string -> object. Keyword arguments
                accumulated by the pipeline thus far.

        Returns:
            Dict of string -> string. Keys are names of form fields; values are
            values for that field. Where there is no value, the empty string
            must be used.
        """
        # Details about the user sent back from the provider.
        details = pipeline_kwargs.get('details')

        # Get the username separately to take advantage of the de-duping logic
        # built into the pipeline. The provider cannot de-dupe because it can't
        # check the state of taken usernames in our system. Note that there is
        # technically a data race between the creation of this value and the
        # creation of the user object, so it is still possible for users to get
        # an error on submit.
        suggested_username = pipeline_kwargs.get('username')

        return {
            'email': cls.get_email(details) or '',
            'name': cls.get_name(details) or '',
            'username': suggested_username,
        }

    @classmethod
    def merge_onto(cls, settings):
        """Merge class-level settings onto a django settings module."""
        for key, value in cls.SETTINGS.iteritems():
            setattr(settings, key, value)


class NpoedBackend(BaseOAuth2):
    name = 'NPOED'
    ID_KEY = 'user_id'
    AUTHORIZATION_URL = 'http://community.npoed.ru/oauth/authorize'
    ACCESS_TOKEN_URL = 'http://community.npoed.ru/oauth/token'
    DEFAULT_SCOPE = []
    REDIRECT_STATE = False
    ACCESS_TOKEN_METHOD = 'POST'

    def get_user_details(self, response):
        """ Return user details from NPOED account. """
        email = response.get('email', '')
        firstname = response.get('firstname', '')
        lastname = response.get('lastname', '')
        fullname = ' '.join([firstname, lastname])
        return {'username': email.split('@', 1)[0],
                'email': email,
                'fullname': fullname,
                'first_name': firstname,
                'last_name': lastname}

    def user_data(self, access_token, *args, **kwargs):
        """ Grab user profile information from NPOED. """
        userinfo = self.get_json('http://community.npoed.ru/api/me',
                                 params={'access_token': access_token})
        email = userinfo['email']
        return {
            'user_id': userinfo['id'],
            'username': email.split('@', 1)[0],
            'email': email,
            'firstname': userinfo['name'],
            'lastname': userinfo['surname'],
        }

    def do_auth(self, access_token, *args, **kwargs):
        """Finish the auth process once the access_token was retrieved"""
        data = self.user_data(access_token)
        data['access_token'] = access_token
        kwargs.update({'response': data, 'backend': self})
        return self.strategy.authenticate(*args, **kwargs)


class NpoedProvider(BaseProvider):
    """ Provider for NPOED Oauth2 auth system. """

    BACKEND_CLASS = NpoedBackend
    NAME = 'NPOED'
    SETTINGS = {
        'SOCIAL_AUTH_NPOED_KEY': None,
        'SOCIAL_AUTH_NPOED_SECRET': None,
    }

    @classmethod
    def get_email(cls, provider_details):
        return provider_details.get('email')

    @classmethod
    def get_name(cls, provider_details):
        return provider_details.get('fullname')

