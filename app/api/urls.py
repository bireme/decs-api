from django.urls import path, re_path, include
from api.thesaurus_term_api import *
from tastypie.api import Api

wsdecs_api = Api(api_name='thesaurus')
wsdecs_api.register(TermResource())

#from api.user_apikey import *
#userapikey_api = Api(api_name='userapikey')
#userapikey_api.register(UserResource())

urlpatterns = [
    # API's
    # Web Service DeCS
    path('', include(wsdecs_api.urls)),
    #path('', include(userapikey_api.urls)),
]
