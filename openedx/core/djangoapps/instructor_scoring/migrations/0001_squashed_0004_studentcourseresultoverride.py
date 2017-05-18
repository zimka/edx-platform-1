# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    replaces = [(b'instructor_scoring', '0001_initial'), (b'instructor_scoring', '0002_auto_20170427_0752'), (b'instructor_scoring', '0003_auto_20170427_0813'), (b'instructor_scoring', '0004_studentcourseresultoverride')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courseware', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentGradeOverride',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('original_grade', models.FloatField(default=0)),
                ('current_grade', models.FloatField(default=0)),
                ('student_module', models.OneToOneField(on_delete=django.db.models.deletion.DO_NOTHING, to='courseware.StudentModule')),
            ],
        ),
        migrations.CreateModel(
            name='StudentCourseResultOverride',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', models.CharField(max_length=100)),
                ('added_percent', models.FloatField()),
                ('passed_sections', models.CharField(max_length=256)),
                ('student', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
