from __future__ import absolute_import, unicode_literals

from django.urls import re_path

from mezzanine.conf import settings

from mezzanine.utils.importing import import_dotted_path


def import_view(dotted_path):
    """
    Import a class or function based view by its dotted path.
    """
    obj = import_dotted_path(dotted_path)
    try:
        return obj.as_view()
    except AttributeError:
        return obj

from . import views

UUID_RE = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

purchase_create_view = import_view(settings.SURVEYS_PURCHASE_CREATE_VIEW)
purchase_report_view = import_view(settings.SURVEYS_PURCHASE_REPORT_VIEW)

urlpatterns = [
    re_path("^purchase/(?P<slug>.*)/$",
            purchase_create_view, name="purchase_create"),
    re_path("^manage/(?P<public_id>%s)/$" % UUID_RE,
            views.SurveyPurchaseDetail.as_view(), name="purchase_detail"),
    re_path("^take/(?P<public_id>%s)/$" % UUID_RE,
            views.SurveyResponseCreate.as_view(), name="response_create"),
    re_path("^take/(?P<public_id>%s)/complete/$" % UUID_RE,
            views.SurveyResponseComplete.as_view(), name="response_complete"),
    re_path("^report/(?P<public_id>%s)/$" % UUID_RE,
            purchase_report_view, name="purchase_report"),
]
