# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-10 10:19

# Django
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Crowdsource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255)),
                (
                    "datetime_created",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("datetime_opened", models.DateTimeField(blank=True, null=True)),
                ("datetime_closed", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("open", "Opened"),
                            ("close", "Closed"),
                        ],
                        default="draft",
                        max_length=9,
                    ),
                ),
                ("description", models.CharField(max_length=255)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crowdsources",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CrowdsourceChoice",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("choice", models.CharField(max_length=255)),
                ("order", models.PositiveSmallIntegerField()),
            ],
            options={"ordering": ("order",)},
        ),
        migrations.CreateModel(
            name="CrowdsourceData",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        help_text="This should be an oEmbed enabled URL", max_length=255
                    ),
                ),
                (
                    "crowdsource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data",
                        to="crowdsource.Crowdsource",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CrowdsourceField",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("label", models.CharField(max_length=255)),
                (
                    "type",
                    models.CharField(
                        choices=[("text", "text"), ("select", "select")], max_length=10
                    ),
                ),
                ("order", models.PositiveSmallIntegerField()),
                (
                    "crowdsource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fields",
                        to="crowdsource.Crowdsource",
                    ),
                ),
            ],
            options={"ordering": ("order",)},
        ),
        migrations.CreateModel(
            name="CrowdsourceResponse",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("datetime", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "crowdsource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="crowdsource.Crowdsource",
                    ),
                ),
                (
                    "data",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="crowdsource.CrowdsourceData",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crowdsource_responses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CrowdsourceValue",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("value", models.CharField(max_length=255)),
                (
                    "field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="values",
                        to="crowdsource.CrowdsourceField",
                    ),
                ),
                (
                    "response",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="values",
                        to="crowdsource.CrowdsourceResponse",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="crowdsourcechoice",
            name="field",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="choices",
                to="crowdsource.CrowdsourceField",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="crowdsourcefield",
            unique_together=set([("crowdsource", "order"), ("crowdsource", "label")]),
        ),
        migrations.AlterUniqueTogether(
            name="crowdsourcechoice",
            unique_together=set([("field", "order"), ("field", "choice")]),
        ),
    ]
