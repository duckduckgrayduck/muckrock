# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-25 15:38


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crowdsource', '0008_auto_20180122_1353'),
    ]

    operations = [
        migrations.AddField(
            model_name='crowdsourcefield',
            name='max',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crowdsourcefield',
            name='min',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='crowdsourcefield',
            name='type',
            field=models.CharField(choices=[(b'text', b'text'), (b'select', b'select'), (b'checkbox2', b'checkbox2'), (b'date', b'date'), (b'number', b'number'), (b'textarea', b'textarea')], max_length=10),
        ),
    ]
