# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import xmodule_django.models


class Migration(migrations.Migration):

    replaces = [(b'instructor_scoring', '0001_initial'), (b'instructor_scoring', '0002_auto_20170427_0752'), (b'instructor_scoring', '0003_auto_20170427_0813'), (b'instructor_scoring', '0004_studentcourseresultoverride'), (b'instructor_scoring', '0005_studentcourseresultoverride_whitelist'), (b'instructor_scoring', '0006_auto_20170517_1405'), (b'instructor_scoring', '0007_auto_20170518_1145'), (b'instructor_scoring', '0008_studentgradeoverwrite_course_id'), (b'instructor_scoring', '0009_auto_20170518_1251'), (b'instructor_scoring', '0010_auto_20170518_1256'), (b'instructor_scoring', '0011_auto_20170518_1305')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('certificates', '0008_schema__remove_badges'),
        ('courseware', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentGradeOverwrite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('original_grade', models.FloatField(default=0)),
                ('current_grade', models.FloatField(default=0)),
                ('student_module', models.OneToOneField(on_delete=django.db.models.deletion.DO_NOTHING, to='courseware.StudentModule')),
                ('location', xmodule_django.models.UsageKeyField(default=None, max_length=255)),
                ('user', models.OneToOneField(default=None, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='studentgradeoverwrite',
            unique_together=set([('user', 'location')]),
        ),
        migrations.RemoveField(
            model_name='studentgradeoverwrite',
            name='student_module',
        ),
        migrations.AddField(
            model_name='studentgradeoverwrite',
            name='course_id',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='studentgradeoverwrite',
            unique_together=set([]),
        ),
        migrations.AlterField(
            model_name='studentgradeoverwrite',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
    ]
