from __future__ import absolute_import, unicode_literals

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import generic

from mezzy.utils.views import FormMessagesMixin, LoginRequiredMixin, UserPassesTestMixin

from ..forms.surveys import SurveyPurchaseForm, SurveyResponseForm
from ..models import SurveyPage, SurveyPurchase, SurveyPurchaseCode


class SurveyPurchaseMixin(object):
    """
    Generic view to get SurveyPurchase intstances by public ID.
    """
    @cached_property
    def purchase(self):
        qs = SurveyPurchase.objects.all() \
            .select_related("survey") \
            .prefetch_related("survey__categories__subcategories__questions")
        return get_object_or_404(qs, public_id=self.kwargs["public_id"])

    def get_context_data(self, **kwargs):
        kwargs.update({
            "purchase": self.purchase,
            "survey": self.purchase.survey,
        })
        return super(SurveyPurchaseMixin, self).get_context_data(**kwargs)


class SurveyPurchaseCreate(LoginRequiredMixin, FormMessagesMixin, generic.CreateView):
    """
    Allows users to purchase surveys.
    """
    form_class = SurveyPurchaseForm
    template_name = "surveys/survey_purchase_create.html"
    success_message = _("You have successfully purchased this survey")
    error_message = _("There was a problem with the purchase process")

    @cached_property
    def survey(self):
        return get_object_or_404(
            SurveyPage.objects.published(for_user=self.request.user),
            slug=self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        kwargs.update({
            "survey": self.survey,
        })
        return super(SurveyPurchaseCreate, self).get_context_data(**kwargs)

    def form_valid(self, form):
        """
        The form is valid, let's process the payment and save the purchase.
        """
        form.instance.survey = self.survey
        form.instance.purchaser = self.request.user

        # Process via purchase code or regular payment
        purchase_code = form.cleaned_data.get("purchase_code")
        try:
            if purchase_code:
                self.process_purchase_code(purchase_code, form)
            else:
                self.process_payment(form)
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        # Code or payment processed successfully, save and continue
        return super(SurveyPurchaseCreate, self).form_valid(form)

    def process_purchase_code(self, purchase_code, form):
        """
        Process a purchase based on code entered by the user.
        """
        try:
            code = self.survey.purchase_codes.get(code=purchase_code, uses_remaining__gt=0)
        except SurveyPurchaseCode.DoesNotExist:
            raise ValidationError(_("The code you entered is not valid"))

        code.uses_remaining = F("uses_remaining") - 1
        try:
            code.save()
        except IntegrityError:  # Raised when uses_remaining becomes negative
            raise ValidationError(_("The code you entered is no longer available"))

        form.instance.amount = 0
        form.instance.transaction_id = purchase_code
        form.instance.payment_method = "Purchase Code"

    def process_payment(self, form):
        """
        By default all purchases are complimentary.
        Payment processors should implement their logic here and set these fields accordingly.
        """
        form.instance.transaction_id = "Complimentary"
        form.instance.payment_method = "Complimentary"
        form.instance.amount = 0


class SurveyPurchaseDetail(UserPassesTestMixin, SurveyPurchaseMixin, generic.TemplateView):
    """
    Allows users to manage a survey they've purchased.
    """
    template_name = "surveys/survey_purchase_detail.html"

    def test_func(self):
        """
        Only allow access to the user that purchased this survey.
        """
        user = self.request.user
        if not user.is_authenticated:
            return False
        return self.purchase.purchaser == user


class SurveyResponseCreate(FormMessagesMixin, SurveyPurchaseMixin, generic.CreateView):
    """
    Allows a user to answer a survey and submit it.
    """
    form_class = SurveyResponseForm
    template_name = "surveys/survey_response_create.html"
    success_message = "Thank you! Your responses have been saved successfully"

    def get_form_kwargs(self):
        kwargs = super(SurveyResponseCreate, self).get_form_kwargs()
        kwargs.update({
            "purchase": self.purchase
        })
        return kwargs

    def get_success_url(self):
        return self.purchase.get_complete_url()


class SurveyResponseComplete(SurveyPurchaseMixin, generic.TemplateView):
    """
    Displays a confirmation message after the user has completed a survey.
    """
    template_name = "surveys/survey_response_complete.html"


class SurveyPurchaseReport(SurveyPurchaseDetail):
    """
    Allow users to generate a report for their survey when requested via POST.
    The report is stored as JSON in the SurveyPurchase and can be retrieved via GET.
    """
    template_name = "surveys/survey_purchase_report.html"

    def post(self, request, *args, **kwargs):
        self.purchase.generate_report()
        messages.success(request, _("Report generated successfully"), fail_silently=True)
        return redirect(self.purchase.get_report_url())
