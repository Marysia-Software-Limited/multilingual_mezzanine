from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from mezzanine.core.translation import (
    TranslatedDisplayable,
    TranslatedRichText,
    TranslatedSlugged,
)

from .models import (
    SurveyPage, SurveyPurchase, SurveyPurchaseCode, Category, Question, SurveyResponse,
    QuestionResponse, Subcategory,
)


@register(SurveyPage)
class SurveyPageTranslationOptions(TranslationOptions):
    fields = ("instructions", "purchase_response", "completed_message", "report_explanation")


@register(SurveyPurchase)
class SurveyPurchaseTranslationOptions(TranslationOptions):
    fields = ()


@register(SurveyPurchaseCode)
class SurveyPurchaseCodeTranslationOptions(TranslationOptions):
    fields = ()


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ("description",)


@register(Question)
class QuestionTranslationOptions(TranslationOptions):
    fields = ()


@register(SurveyResponse)
class SurveyResponseTranslationOptions(TranslationOptions):
    fields = ()


@register(QuestionResponse)
class QuestionResponseTranslationOptions(TranslationOptions):
    fields = ("text_response",)


@register(Subcategory)
class SubcategoryTranslationOptions(TranslationOptions):
    fields = ("description",)

