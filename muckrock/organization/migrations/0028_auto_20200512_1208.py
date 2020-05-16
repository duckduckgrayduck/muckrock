# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2020-05-12 16:08
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0027_organization_avatar_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='Entitlement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('description', models.TextField()),
                ('resources', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
            ],
        ),
        migrations.AddField(
            model_name='organization',
            name='entitlement',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='organization.Entitlement'),
        ),
    ]
