# coding=utf-8
import json
import urllib2
import logging

from lxml.etree import Element, SubElement
from django.conf import settings
import requests

log = logging.getLogger(__name__)

EVMS_URL = None
if hasattr(settings, 'EVMS_URL'):
    EVMS_URL = 'https://evms.openedu.ru'


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


def _edx_openedu_compare(openedu_profile, edx_profile):
    """
    Openedu api возвращает по edx_id url со значениями profile: 'original' и 'hd'.
    EDX для отображения ожидает profile из ['youtube', 'desktop_webm', 'desktop_mp4'].
    Проверяет 'равны' ли значения
    :param openedu_profile:
    :param edx_profile:
    :return:
    """
    mapping = {
        "desktop_mp4": "desktop_mp4",
        "SD": "desktop_webm",
        "sd": "desktop_webm",
        "HD": "desktop_mp4",
        "hd": "desktop_mp4",
        "hd2": "desktop_mp4",
    }
    if openedu_profile == edx_profile:
        return True
    if openedu_profile in mapping:
        if mapping[openedu_profile] == edx_profile:
            return True
    else:
        log.error("Unknown video evms format: {}".format(openedu_profile))
    return False


def get_urls_for_profiles(edx_video_id, val_profiles):
    raw_data = get_video_info(edx_video_id)
    if raw_data is None:
        raw_data = {}
    profile_data = {}
    for profile in val_profiles:
        url = ''
        if 'encoded_videos' in raw_data:
            videos = raw_data['encoded_videos']
            for video in videos:
                if _edx_openedu_compare(video.get('profile'), profile):
                    url = video.get('url', '')
        profile_data[profile] = url
    return profile_data


def get_url_for_profile(edx_video_id, val_profile):
    return get_urls_for_profiles(edx_video_id, [val_profile])[val_profile]


def get_video_info(edx_video_id):
    token = None
    if hasattr(settings, 'EVMS_API_KEY'):
        token = getattr(settings, 'EVMS_API_KEY')
    url_api = u'{0}/api/v2/video/{1}?token={2}'.format(EVMS_URL, edx_video_id, token)
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
        if isinstance(video, list):
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


def get_video_info_for_course_and_profiles(course_id, video_profile_names):
    return {}


def get_course_evms_guid(course_id):
    return str(course_id).split('+')[1]


def get_course_edx_val_ids(course_id):
    token = getattr(settings, 'EVMS_API_KEY')
    course_vids_api_url = '{0}/api/v2/course'.format(EVMS_URL)  #только при исполнении, чтобы не было конфликтов при paver update_assets
    course_guid = get_course_evms_guid(course_id)
    url_api = u'{0}/{1}?token={2}'.format(course_vids_api_url, course_guid, token)
    try:
        videos = requests.get(url_api).json().get("videos", False)
    except Exception as e:
        log.error("Api Exception:{}".format(str(e)))
        return False
    if not videos:
        return False
    values = []
    for v in videos:
        _dict = {"display_name": v["client_video_id"], "value": v["edx_video_id"]}
        values.append(_dict)
    return values
