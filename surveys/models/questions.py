# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from django.db import models

from django.utils.translation import gettext_lazy as _

from mezzanine.core.fields import RichTextField
from mezzanine.core.models import Orderable, TimeStamped

from mezzy.utils.models import TitledInline

from ..managers import RatingDataQuerySet, QuestionResponseQuerySet


class Category(TitledInline):
    """
    A Category that contains one or more Subcategories.
    """
    survey = models.ForeignKey(
        "surveys.SurveyPage", on_delete=models.CASCADE, related_name="categories")
    description = RichTextField(_("Description"))

    objects = RatingDataQuerySet.as_manager()

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def get_rating_data(self, purchase):
        """
        Returns a serializable object with rating data for this category.
        """
        rating_responses = QuestionResponse.objects.filter(
            question__subcategory__category=self,
            question__field_type=Question.RATING_FIELD,
            response__purchase=purchase)

        count = rating_responses.count()
        if not count:
            return None  # Don't return data if no rating responses exist

        return {
            "id": self.pk,
            "title": self.title,
            "description": self.description,
            "rating": {
                "count": count,
                "average": rating_responses.get_average(),
                "frequencies":
                    rating_responses.get_frequencies(purchase.survey.get_rating_choices()),
            },
            "subcategories": self.subcategories.get_rating_data(purchase),
        }


class Subcategory(TitledInline):
    """
    A Subcategory that contains one or more Questions.
    """
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    description = RichTextField(_("Description"))

    objects = RatingDataQuerySet.as_manager()

    class Meta:
        verbose_name = _("subcategory")
        verbose_name_plural = _("subcategories")

    def get_rating_data(self, purchase):
        """
        Returns a serializable object with rating data for this subcategory.
        """
        rating_responses = QuestionResponse.objects.filter(
            question__subcategory=self,
            question__field_type=Question.RATING_FIELD,
            response__purchase=purchase)

        count = rating_responses.count()
        if not count:
            return None  # Don't return data if no rating responses exist

        return {
            "id": self.pk,
            "title": self.title,
            "description": self.description,
            "rating": {
                "count": count,
                "average": rating_responses.get_average(),
                "frequencies":
                    rating_responses.get_frequencies(purchase.survey.get_rating_choices()),
            },
            "questions": self.questions.get_rating_data(purchase),
        }


# @python_2_unicode_compatible
class Question(Orderable):
    """
    A question on a SurveyPage.
    """
    RATING_FIELD = 1
    TEXT_FIELD = 2
    QUESTION_TYPES = (
        (RATING_FIELD, "Rating"),
        (TEXT_FIELD, "Text"),
    )

    subcategory = models.ForeignKey(
        Subcategory, on_delete=models.CASCADE, related_name="questions")
    field_type = models.IntegerField(_("Question type"), choices=QUESTION_TYPES)
    prompt = models.CharField(_("Prompt"), max_length=300)
    required = models.BooleanField(_("Required"), default=True)
    invert_rating = models.BooleanField(_("Invert rating"), default=False)

    objects = RatingDataQuerySet.as_manager()

    class Meta:
        verbose_name = _("question")
        verbose_name_plural = _("questions")

    def __str__(self):
        return self.prompt

    def get_rating_data(self, purchase):
        """
        Returns a serializable object with rating data for this question.
        """
        rating_responses = QuestionResponse.objects.filter(
            question=self,
            question__field_type=Question.RATING_FIELD,
            response__purchase=purchase)

        count = rating_responses.count()
        if not count:
            return None  # Don't return data if no rating responses exist

        return {
            "id": self.pk,
            "prompt": self.prompt,
            "invert_rating": self.invert_rating,
            "rating": {
                "count": count,
                "average": rating_responses.get_average(),
                "frequencies":
                    rating_responses.get_frequencies(purchase.survey.get_rating_choices()),
            },
        }


# @python_2_unicode_compatible
class SurveyResponse(TimeStamped):
    """
    Collection of all responses related to a Purchase.
    """
    purchase = models.ForeignKey(
        "surveys.SurveyPurchase", related_name="responses", on_delete=models.CASCADE)

    def __str__(self):
        return str(self.created)


# @python_2_unicode_compatible
class QuestionResponse(models.Model):
    """
    Response to a single Question.
    """
    response = models.ForeignKey(
        SurveyResponse, related_name="responses", on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name="responses", on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(_("Rating"), blank=True, null=True)
    text_response = models.TextField(_("Text response"), blank=True)

    objects = QuestionResponseQuerySet.as_manager()

    def __str__(self):
        if self.rating is not None:
            return str(self.rating)
        return self.text_response

    def normalize_rating(self):
        """
        Invert the rating if the question requires it.
        """
        if self.rating is not None and self.question.invert_rating:
            max_rating = self.question.subcategory.category.survey.max_rating
            self.rating = max_rating - int(self.rating) + 1
