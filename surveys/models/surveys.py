# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json
import uuid

from builtins import range

from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
# from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from mezzanine.conf import settings
from mezzanine.core.fields import RichTextField
from mezzanine.core.models import RichText, TimeStamped
from mezzanine.pages.models import Page

from ..managers import SurveyPurchaseQuerySet


class SurveyPage(Page, RichText):
    """
    Survey that's available for purchase.
    """
    instructions = RichTextField(_("Instructions"))
    cost = models.DecimalField(_("Cost"), max_digits=7, decimal_places=2, default=0)
    purchase_response = RichTextField(_("Purchase response"))
    completed_message = RichTextField(
        _("Completed message"),
        help_text=_("Message shown to users after completing the survey"))

    max_rating = models.PositiveSmallIntegerField(
        _("Maximum rating"), default=5,
        validators=[MinValueValidator(2), MaxValueValidator(10)],
        help_text=_("For rating questions. Must be a number between 2 and 10"))
    report_explanation = RichTextField(
        _("Explanation"),
        help_text=_("Helping content shown before the results' detail"))

    def get_questions(self):
        """
        Collect all questions related to this survey.
        """
        from .questions import Question
        return Question.objects.filter(subcategory__category__survey=self)

    def get_rating_choices(self):
        return range(1, self.max_rating + 1)

    def get_requires_payment(self):
        return self.cost > 0

    class Meta:
        verbose_name = _("survey page")
        verbose_name_plural = _("survey pages")


# @python_2_unicode_compatible
class SurveyPurchaseCode(models.Model):
    """
    Code to gain access to a Survey without paying.
    """
    survey = models.ForeignKey(SurveyPage, related_name="purchase_codes", on_delete=models.CASCADE)
    code = models.CharField(
        _("Code"), max_length=20, blank=True,
        help_text=_("If left blank it will be automatically generated"))
    uses_remaining = models.PositiveIntegerField(_("Remaining uses"), default=0)

    class Meta:
        verbose_name = _("purchase code")
        verbose_name_plural = _("purchase codes")
        unique_together = ("survey", "code")

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        """
        Generate a UUID if the code hasn't been defined
        """
        if not self.code:
            self.code = str(uuid.uuid4()).strip("-")[4:23]
        super(SurveyPurchaseCode, self).save(*args, **kwargs)


# @python_2_unicode_compatible
class SurveyPurchase(TimeStamped):
    """
    A record of a user purchasing a Survey.
    """
    survey = models.ForeignKey(SurveyPage, on_delete=models.CASCADE, related_name="purchases")
    purchaser = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="survey_purchases")
    public_id = models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)

    transaction_id = models.CharField(_("Transaction ID"), max_length=200, blank=True)
    payment_method = models.CharField(_("Payment method"), max_length=100, blank=True)
    amount = models.DecimalField(
        _("Amount"), max_digits=8, decimal_places=2, blank=True, null=True)
    notes = models.TextField(_("Notes"), blank=True)

    report_generated = models.DateTimeField(_("Report generated"), blank=True, null=True)
    report_cache = models.TextField(_("Report (cached)"), default="[]")

    objects = SurveyPurchaseQuerySet.as_manager()

    class Meta:
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")

    def __str__(self):
        return str(self.survey)

    def get_absolute_url(self):
        return reverse("surveys:purchase_detail", args=[self.public_id])

    def get_response_create_url(self):
        return reverse("surveys:response_create", args=[self.public_id])

    def get_complete_url(self):
        return reverse("surveys:response_complete", args=[self.public_id])

    def get_report_url(self):
        return reverse("surveys:purchase_report", args=[self.public_id])

    def generate_report(self):
        """
        Generate a report of all responses related to this purchase.
        A cached copy will be stored in self.report_cache.
        The report includes nested data in the shape of Category / Subcategory / Question.
        """
        from .questions import Question, QuestionResponse
        rating_responses = QuestionResponse.objects.filter(
            response__purchase=self, question__field_type=Question.RATING_FIELD)

        text_questions = []
        for question in self.survey.get_questions().filter(field_type=Question.TEXT_FIELD):
            responses = question.responses.filter(response__purchase=self)
            text_questions.append({
                "id": question.pk,
                "prompt": question.prompt,
                "responses": list(responses.values_list("text_response", flat=True)),
            })

        report = {
            "rating": {
                "count": rating_responses.count(),
                "average": rating_responses.get_average(),
                "frequencies": rating_responses.get_frequencies(self.survey.get_rating_choices()),
            },
            "categories": self.survey.categories.get_rating_data(purchase=self),
            "text_questions": text_questions,
        }
        self.report_cache = json.dumps(report)
        self.report_generated = now()
        self.save()
        return report

    def get_report_as_json(self):
        """
        Load the cached report as JSON.
        """
        return json.loads(self.report_cache)
