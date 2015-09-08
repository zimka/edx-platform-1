import json
import urllib2
import logging

from lxml.etree import Element, SubElement
from django.conf import settings

log = logging.getLogger(__name__)
API_URL = '{0}/api/v1/video'.format(getattr(settings, 'EVMS_URL'))


class ValError(Exception):
    """
    An error that occurs during VAL actions.
    This error is raised when the VAL API cannot perform a requested
    action.
    """
    pass


class ValInternalError(ValError):
    """
    An error internal to the VAL API has occurred.
    This error is raised when an error occurs that is not caused by incorrect
    use of the API, but rather internal implementation of the underlying
    services.
    """
    pass


class ValVideoNotFoundError(ValError):
    """
    This error is raised when a video is not found
    If a state is specified in a call to the API that results in no matching
    entry in database, this error may be raised.
    """
    pass


class ValVideoNotFoundError(ValError):
    """
    This error is raised when a video is not found
    If a state is specified in a call to the API that results in no matching
    entry in database, this error may be raised.
    """
    pass


class ValCannotCreateError(ValError):
    """
    This error is raised when an object cannot be created
    """
    pass


def get_urls_for_profiles(edx_video_id, val_profiles):
    raw_data = get_video_info(edx_video_id)
    if raw_data is None:
        raw_data = {}
    else:
        raw_data = raw_data[0]
    log.warning(raw_data)
    profile_data = {}
    for profile in val_profiles:
        url = ''
        if 'encoded_videos' in raw_data:
            videos = raw_data['encoded_videos']
            for video in videos:
                if video.get('profile') == profile:
                    url = video.get('url', '')
        profile_data[profile] = url
    return json.loads(json.dumps(profile_data))


def get_url_for_profile(edx_video_id, val_profile):
    return get_urls_for_profiles(edx_video_id, [val_profile])[val_profile]


def get_video_info(edx_video_id):
    token = getattr(settings, 'EVMS_API_KEY')
    url_api = u'{0}/{1}?token={2}'.format(API_URL, edx_video_id, token)
    try:
        response = urllib2.urlopen(url_api)
    except:
        return None
    data = response.read()
    clean_data = json.loads(data)
    return clean_data


def export_to_xml(edx_video_id):
    video = get_video_info(edx_video_id)
    if video is None:
        return Element('video_asset')
    else:
        video = video[0]
    video_el = Element(
        'video_asset',
        attrib={
            'client_video_id': video['client_video_id'],
            'duration': unicode(video['duration']),
        }
    )
    for encoded_video in video['encoded_videos']:
        SubElement(
            video_el,
            'encoded_video',
            {
                name: unicode(encoded_video.get(name))
                for name in ['profile', 'url', 'file_size', 'bitrate']
            }
        )
    # Note: we are *not* exporting Subtitle data since it is not currently updated by VEDA or used
    # by LMS/Studio.
    return video_el


def import_from_xml(xml, edx_video_id, course_id=None):
    return
