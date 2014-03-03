from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.conf.urls import include
from fastapp.views import DjendBaseView, DjendBaseSaveView, DjendBaseDeleteView, DjendExecSaveView, \
                DjendBaseCreateView, DjendExecDeleteView, DjendExecView, DjendStaticView, \
                login_or_sharedkey, dropbox_auth_finish, dropbox_auth_start, DjendView, \
                DjendBaseSettingsView, DjendBaseRenameView
from rest_framework import viewsets, routers

from fastapp.models import Base, Apy
from fastapp.api_views import *



# Routers provide an easy way of automatically determining the URL conf
router = routers.DefaultRouter(trailing_slash=True)
router.register(r'apy', ApyViewSet)
router.register(r'base', BaseViewSet)

urlpatterns = patterns('',

    # dropbox auth
    url(r'dropbox_auth_start/?$',dropbox_auth_start),
    url(r'dropbox_auth_finish/?$',dropbox_auth_finish),

    # base
    url(r'(?P<base>[\w-]+)/index/$', login_required(DjendBaseView.as_view())),
    url(r'(?P<base>[\w-]+)/sync/$', login_required(DjendBaseSaveView.as_view())),
    url(r'(?P<base>[\w-]+)/new/$', login_required(DjendBaseCreateView.as_view())),
    url(r'(?P<base>[\w-]+)/delete/$', login_required(DjendBaseDeleteView.as_view())),
    url(r'(?P<base>[\w-]+)/rename/$', login_required(DjendBaseRenameView.as_view())),

    # settings
    #url(r'(?P<base>[\w-]+)/kv/$', login_required(DjendBaseSettingsView.as_view())),
    #url(r'(?P<base>[\w-]+)/kv/(?P<id>[\w-]+)/$', login_required(DjendBaseSettingsView.as_view())),

    # execs
    #url(r'(?P<base>[\w-]+)/create_exec/$', login_required(DjendExecSaveView.as_view())),
    url(r'(?P<base>[\w-]+)/exec/(?P<id>\w+)/$', \
                                            login_or_sharedkey(DjendExecView.as_view())),
    url(r'(?P<base>[\w-]+)/delete/(?P<id>\w+)/$', \
                                            login_required(DjendExecDeleteView.as_view())),
    #url(r'(?P<base>[\w-]+)/clone/(?P<id>\w+)/$', \
    #                                        login_required(DjendExecCloneView.as_view())),
    #url(r'(?P<base>[\w-]+)/rename/(?P<id>\w+)/$', \
    #                                        login_required(DjendExecRenameView.as_view())),
    # static
    url(r'(?P<base>[\w-]+)/static/(?P<name>.+)$', \
                                            login_or_sharedkey(DjendStaticView.as_view())),
    # api
    url(r'^api/base/$', BaseViewSet.as_view({'get': 'list', 'post': 'create'}), name='base-list'),
    url(r'^api/base/(?P<pk>\d+)/$', BaseViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='base-detail'),
    url(r'^api/base/(?P<base_pk>\d+)/apy/$', ApyViewSet.as_view({'get': 'list', 'post': 'create'}), name='apy-list'),
    url(r'^api/base/(?P<base_pk>\d+)/apy/(?P<pk>\d+)/$', ApyViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='apy-detail'),
    url(r'^api/base/(?P<base_pk>\d+)/apy/(?P<pk>\d+)/clone/$', ApyViewSet.as_view({'post': 'clone'}), name='apy-clone'),
    url(r'^api/base/(?P<base_pk>\d+)/setting/$', SettingViewSet.as_view({'get': 'list', 'post': 'create'}), name='apy-list'),
    url(r'^api/base/(?P<base_pk>\d+)/setting/(?P<pk>\d+)/$', SettingViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='apy-detail'),

    # home
    url(r'^$', DjendView.as_view()),
)

from rest_framework.urlpatterns import format_suffix_patterns
urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'api'])
