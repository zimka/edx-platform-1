# -*- coding: utf-8 -*-
import json
import re
import urllib
from collections import namedtuple
import time

Report = namedtuple("Report", ["name", "head", "body", "warnings"])


def _build_items_tree(items):
    """Построение дерева курса с корнем в итеме с category='course'"""
    course_root = None
    for num, i in enumerate(items):
        if i.category=="course":
            course_root = num
    if course_root is None:
        raise ValueError("No course in {}".format([i.category for i in items]))
    edges = []
    ids = [i.url_name for i in items]

    def deep_search(item_num):
        item = items[item_num]
        children_ids = [x.url_name for x in item.get_children()]
        children_nums = [num for num, x in enumerate(ids) if x in children_ids]
        for c in children_nums:
            edges.append([item_num, c])
            deep_search(c)

    deep_search(course_root)
    return course_root, edges


def _print_all(item):
    ats = dir(item)
    for at in ats:
        try:
            t = getattr(item, at)
            if callable(t):
                print(at, "callable")
            else:
                print(at, t)
        except Exception as e:
            print(at, e.message)


def secs2readable(secs):
    if not isinstance(secs, int):
        try:
            secs = int(secs)
        except ValueError:
            return secs
    if secs > 3599: #Больше часа
        parse = "%H:%M:%S"
    else:
        parse = "%M:%S"
    readable = time.strftime(parse, time.gmtime(secs))
    return readable


def youtube_duration(video_id):
    """ ATTENTION! В функции используется youtube_api. Необходим
    api_key. Для получения api_key:
    1.Зарегистрироваться на console.developers.google.com
    2. на главной YouTube API >YouTube Data API
    3. Включить Youtube Api
    4. В учетных данных (Credentials) взять ключ

    Определяет длительность видео с YouTube по video_id, гда
    video_id это часть url: https://youtu.be/$video_id$"""
    if not video_id:
        return None
    api_key = "AIzaSyCnxGGegKJ1_R-cEVseGUrAcFff5VHXgZ0"
    searchUrl = "https://www.googleapis.com/youtube/v3/videos?id=" + video_id + "&key=" + api_key + "&part=contentDetails"
    try:
        response = urllib.urlopen(searchUrl).read()
    except IOError:
        return unicode("No response from server.")
    data = json.loads(response)
    if data.get('error', False):
        return u"Error while video duration check:{}".format(data['error'])
    all_data = data['items']
    if  not len(all_data):
        return u"Can't find video with such id on youtube."

    contentDetails = all_data[0]['contentDetails']
    duration = contentDetails['duration']
    temp = re.split(r'(\d+)', duration)
    times = filter(lambda x: x.isdigit(), temp)
    if len(times) > 3:
            return u"Is this video longer than one 24 hours?"
    dur = unicode(secs2readable(sum([int(x)*60**num for num, x in enumerate(reversed(times))])))
    return dur


def edx_id_duration(edx_video_id):
    """Определяет длительность видео по предоставленному edx_video_id"""
    if not edx_video_id:
        return None
    try:
        from openedx.core.djangoapps.video_evms.api import get_video_info
    except ImportError:
        return u"Can't check edx video id: no api"
    video = get_video_info(edx_video_id)
    if not video:
        return unicode("No response from server.")
    if not video:
        return u"No video for this edx_video_id:{}".format(edx_video_id)
    temp = video.get('duration', "Error: didn't get duration from server")
    num = int(float(temp))
    return unicode(secs2readable(num))