from __future__ import absolute_import, unicode_literals

from mezzanine.conf import register_setting

register_setting(
    name="SURVEYS_PURCHASE_CREATE_VIEW",
    default="surveys.views.SurveyPurchaseCreate",
    editable=False,
)

register_setting(
    name="SURVEYS_PURCHASE_REPORT_VIEW",
    default="surveys.views.SurveyPurchaseReport",
    editable=False,
)
