import urllib
import urllib2
import random
import json

import unittest

# TODO: rewrite to use testing mongobase
BASE_URL = 'http://127.0.0.1:8001'
API_URL = '{0}/api/npoed_course_api/v0/courses/'.format(BASE_URL)


def encode_course_data(user_email, org, course_run, course_number):
    data = urllib.urlencode({
        'mode': 'create',
        'course_details': {
            'user_email': user_email,
            'org': org,
            'course_run': course_run,
            'course_name': 'Name of the course',
            'course_number': course_number
        }
    })
    return data


class CourseCreateTest(unittest.TestCase):
    NUMBER = random.randint(1, 100000)

    def test_create_course(self):
        org = 'test'
        course_run = 'test'
        course_number = 'test{}'.format(self.NUMBER)
        user_email = 'martynovp@gmail.com'

        data = encode_course_data(user_email, org, course_run, course_number)

        # test ok
        content = urllib2.urlopen(url=API_URL, data=data).read()
        self.assertEqual(json.loads(json.loads(content))['message'],
                         "Course with id {0}/{1}/{2} successfully created!".format(
            org,
            course_number,
            course_run)
        )

        # test duplicate
        content = urllib2.urlopen(url=API_URL, data=data).read()
        self.assertEqual(json.loads(json.loads(content))['error'],
                         "Course with parameters {0}/{1}/{2} already exists".format(
            org,
            course_number,
            course_run)
        )

        # test bad data
        bad_data = urllib.urlencode({
            'mode': 'create',
            'course_details': {
                'user_email': user_email,
                'course_run': course_run,
                'course_name': 'Name of the course',
                'course_number': course_number
            }
        })
        content = urllib2.urlopen(url=API_URL, data=bad_data).read()
        self.assertEqual(json.loads(json.loads(content))['error'], "You must specify org, course_number and course_run")

        # test bad user
        user_email = 'bad@email.com'
        data = encode_course_data(user_email, org, course_run, course_number)
        content = urllib2.urlopen(url=API_URL, data=data).read()
        self.assertEqual(json.loads(json.loads(content))['error'], "User with email {} not found".format(user_email))


if __name__ == '__main__':
    unittest.main()
