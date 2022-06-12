from __future__ import absolute_import, unicode_literals

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

try:
    import authorize
except ImportError:
    raise ImproperlyConfigured(
        "Install the py-authorize package to use Authorize.net payment gateway")

from mezzanine.conf import settings

from ..forms.surveys import SurveyPurchaseForm
from ..views import SurveyPurchaseCreate


class AuthorizenetSurveyPurchaseForm(SurveyPurchaseForm):
    """
    Collection of fields required by Authorize.net.
    """
    card_number = forms.IntegerField(label=_("Card number"), required=False)
    card_expiry = forms.CharField(label=_("Card expiration"), required=False, help_text=_("MM/YY"))
    card_ccv = forms.IntegerField(label=_("Card CCV"), required=False)

    def clean(self):
        """
        Require card details if no purchase code is provided.
        """
        cleaned_data = super(AuthorizenetSurveyPurchaseForm, self).clean()
        if cleaned_data.get("purchase_code"):
            return cleaned_data

        for f in ["card_number", "card_expiry", "card_ccv"]:
            if not cleaned_data.get(f):
                self.add_error(f, "Required for card payments")
        return cleaned_data


class AuthorizenetSurveyPurchaseCreate(SurveyPurchaseCreate):
    """
    Creates new SurveyPurchases by processing payments with Authorize.net.
    """

    def get_form_class(self):
        """
        Only use the Authorize.net form if payment is required.
        """
        if self.survey.get_requires_payment():
            return AuthorizenetSurveyPurchaseForm
        return super(AuthorizenetSurveyPurchaseCreate, self).get_form_class()

    def dispatch(self, *args, **kwargs):
        """
        Authenticate with Authorize.net early on the view lifecycle.
        Credential errors will surface on GET, before they are critical.
        """
        try:
            LOGIN = settings.AUTHORIZE_NET_LOGIN
            KEY = settings.AUTHORIZE_NET_TRANS_KEY
        except AttributeError:
            raise ImproperlyConfigured(
                "You need to define AUTHORIZE_NET_LOGIN and AUTHORIZE_NET_TRANS_KEY in "
                "your settings module to use the Authorize.net payment processor")

        ENV = authorize.Environment.TEST
        if not getattr(settings, "AUTHORIZE_NET_TEST_MODE", True):
            ENV = authorize.Environment.PRODUCTION
        authorize.Configuration.configure(ENV, LOGIN, KEY)

        return super(AuthorizenetSurveyPurchaseCreate, self).dispatch(*args, **kwargs)

    def process_payment(self, form):
        """
        Call the Authorize.net API to process the payment.
        ValidationErrors will be shown to the user and cancel the purchase.
        """
        # Let the default processor handle surveys that don't require payment
        if not self.survey.get_requires_payment():
            return super(AuthorizenetSurveyPurchaseCreate, self).process_payment(form)

        user = self.request.user
        try:
            charge = authorize.Transaction.sale({
                "amount": self.survey.cost,
                "email": user.email,
                "credit_card": {
                    "card_number": str(form.cleaned_data["card_number"]),
                    "card_code": str(form.cleaned_data["card_ccv"]),
                    "expiration_date": str(form.cleaned_data["card_expiry"]),
                },
                "billing": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
            })

        # Show any Authorize.net errors to the user
        except authorize.exceptions.AuthorizeError as exception:
            try:
                # Unpack exceptions with multiple error messages (AuthorizeInvalidError)
                errors = []
                for code, msg in exception.asdict().items():
                    errors.append(forms.ValidationError(msg, code=code))
                raise forms.ValidationError(errors)
            except AttributeError:
                # Exception doesn't implement asdict() (AuthorizeError)
                raise forms.ValidationError(str(exception))

        # On success, save the transaction details to the form instance
        form.instance.amount = self.survey.cost
        form.instance.payment_method = "Authorize.Net"
        try:
            form.instance.transaction_id = charge["transaction_response"]["trans_id"]
        except KeyError:
            form.instance.transaction_id = "Unknown"
