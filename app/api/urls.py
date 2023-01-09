from django.urls import path, re_path, include
from api.thesaurus_term_api import *
from api.thesaurus_quickterm_api import *
from tastypie.api import Api

wsdecs_api = Api(api_name='thesaurus')
wsdecs_api.register(TermResource())
wsdecs_api.register(QuickTermResource())

urlpatterns = [
    # API's
    # Web Service DeCS
    path('', include(wsdecs_api.urls)),
]
