from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url

urlpatterns = [
    url("^surveys/", include("surveys.urls", namespace="surveys")),
]
