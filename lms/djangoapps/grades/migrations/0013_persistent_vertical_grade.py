# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import lms.djangoapps.grades.models
import coursewarehistoryextended.fields
import django.utils.timezone
import openedx.core.djangoapps.xmodule_django.models
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0012_computegradessetting'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersistentVerticalGrade',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('id', coursewarehistoryextended.fields.UnsignedBigIntAutoField(serialize=False, primary_key=True)),
                ('user_id', models.IntegerField()),
                ('course_id', openedx.core.djangoapps.xmodule_django.models.CourseKeyField(max_length=255)),
                ('usage_key', openedx.core.djangoapps.xmodule_django.models.UsageKeyField(max_length=255)),
                ('subtree_edited_timestamp', models.DateTimeField(null=True, verbose_name='Last content edit timestamp', blank=True)),
                ('course_version', models.CharField(max_length=255, verbose_name='Guid of latest course version', blank=True)),
                ('earned_all', models.FloatField()),
                ('possible_all', models.FloatField()),
                ('earned_graded', models.FloatField()),
                ('possible_graded', models.FloatField()),
                ('weight', models.FloatField()),
                ('first_attempted', models.DateTimeField(null=True, blank=True)),
                ('visible_blocks', models.ForeignKey(to='grades.VisibleBlocks', db_column=b'visible_blocks_hash', to_field=b'hashed')),
            ],
            bases=(lms.djangoapps.grades.models.DeleteGradesMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='persistentverticalgrade',
            unique_together=set([('course_id', 'user_id', 'usage_key')]),
        ),
        migrations.AlterIndexTogether(
            name='persistentverticalgrade',
            index_together=set([('modified', 'course_id', 'usage_key'), ('first_attempted', 'course_id', 'user_id')]),
        ),
    ]
