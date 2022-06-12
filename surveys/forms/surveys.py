from __future__ import absolute_import, unicode_literals

from django import forms
from django.utils.translation import gettext_lazy as _

from mezzy.utils.forms import UXFormMixin

from ..models import SurveyPurchase, SurveyResponse, Question, QuestionResponse


class SurveyPurchaseForm(UXFormMixin, forms.ModelForm):
    """
    Allows users to purchase surveys (via purchase code or traditional payment).
    """
    purchase_code = forms.CharField(label=_("Purchase Code"), required=False)

    class Meta:
        model = SurveyPurchase
        fields = []  # No model fields are user-editable


class SurveyResponseForm(forms.ModelForm):
    """
    Allows users to answer survey questions.
    """

    class Meta:
        model = SurveyResponse
        fields = []  # No model fields are user-editable

    def __init__(self, *args, **kwargs):
        """
        Create dynamic fields for each question in the SurveyPage.
        """
        self.purchase = kwargs.pop("purchase")
        self.questions = self.purchase.survey.get_questions().order_by("field_type")
        super(SurveyResponseForm, self).__init__(*args, **kwargs)

        for question in self.questions:
            field_key = "question_%s" % question.pk

            if question.field_type == Question.RATING_FIELD:
                field = forms.ChoiceField(
                    label=question.prompt,
                    widget=forms.RadioSelect,
                    choices=((i, i) for i in self.purchase.survey.get_rating_choices()))
                field.type = "choicefield"  # Required to apply the right CSS rules
            elif question.field_type == Question.TEXT_FIELD:
                field = forms.CharField(label=question.prompt, widget=forms.Textarea)

            # Use the HTML5 required attribute
            if question.required:
                field.widget.attrs["required"] = ""

            self.fields[field_key] = field

    def save(self, *args, **kwargs):
        """
        Create a QuestionResponse for each Question.
        """
        self.instance.purchase = self.purchase
        survey_response = super(SurveyResponseForm, self).save(*args, **kwargs)

        if survey_response.pk is None:
            return survey_response  # Bail if the SurveyResponse wasn't saved to the DB

        question_responses = []
        for question in self.questions:
            value = self.cleaned_data.get("question_%s" % question.pk)
            response = QuestionResponse(
                response=survey_response,
                question=question,
                rating=value if question.field_type == Question.RATING_FIELD else None,
                text_response=value if question.field_type == Question.TEXT_FIELD else ""
            )
            response.normalize_rating()
            question_responses.append(response)
        QuestionResponse.objects.bulk_create(question_responses)

        return survey_response
