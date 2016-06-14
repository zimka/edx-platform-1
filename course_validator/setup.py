from setuptools import setup

setup(
    name='xblock_course_validator',
    version='0.1',
    description='XBlock CourseValidator',
    py_modules=['xblock_course_validator'],
    install_requires=['XBlock'],
    entry_points={
        'xblock.v1': [
            'xblock_course_validator = course_validator:CourseValidator',
        ]
    }
)