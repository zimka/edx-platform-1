# -*- coding: utf-8 -*-
import base64
from django.conf import settings
from django.contrib.auth import get_user_model


User = get_user_model()


def openedu_email(html_msg, plaintext_msg, email, course_email, course_title, course_url):
    to_course_html_msg = \
        u'<br/><p>Вы получили это письмо, потому что записаны на курс "{0}" на платформе "Открытое образование". ' \
        u'Чтобы продолжить обучение, перейдите <a href="{1}courseware">по ссылке.</a></p>'.format(
            course_title,
            course_url
        )
    to_course_plaintext_msg = \
        u'Вы получили это письмо, потому что записаны на курс "{0}" на платформе "Открытое образование". Чтобы ' \
        u'продолжить обучение, перейдите по по ссылке {1}courseware.'.format(
            course_title,
            course_url
        )

    html_msg = u"{} {}".format(html_msg, to_course_html_msg)
    plaintext_msg = u"{} {}".format(plaintext_msg, to_course_plaintext_msg)
    unsub_headers = {}
    username = User.objects.filter(email=email)[0].username
    unsub_hash = base64.b64encode("{0}+{1}".format(username, course_email.course_id.html_id()))
    unsub_url = '%s%s' % ("{}/unsubscribe/".format(settings.PLP_URL), unsub_hash)
    unsub_headers['List-Unsubscribe'] = '<{0}>'.format(unsub_url)

    html_msg = u'{0}Для отписки от рассылки курса перейдите <a href="{1}">по ссылке.</a>'.format(html_msg, unsub_url)
    plaintext_msg = u'{0}Для отписки от рассылки курса перейдите по ссылке {1}.'.format(plaintext_msg, unsub_url)

    return html_msg, plaintext_msg, unsub_headers