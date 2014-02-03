from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from fastapp.views import DjendBaseView, DjendBaseSaveView, DjendBaseDeleteView, DjendExecCloneView, DjendExecSaveView, DjendBaseCreateView, DjendExecDeleteView, DjendExecView, DjendStaticView, \
                login_or_sharedkey, dropbox_auth_finish, dropbox_auth_start, DjendView, DjendBaseSettingsView

urlpatterns = patterns('',

    url(r'dropbox_auth_start/?$',dropbox_auth_start),
    url(r'dropbox_auth_finish/?$',dropbox_auth_finish),

    url(r'(?P<base>[\w-]+)/index/$', login_or_sharedkey(DjendBaseView.as_view())),
    url(r'(?P<base>[\w-]+)/sync/$', login_required(DjendBaseSaveView.as_view())),
    url(r'(?P<base>[\w-]+)/new/$', login_required(DjendBaseCreateView.as_view())),
    url(r'(?P<base>[\w-]+)/delete/$', login_required(DjendBaseDeleteView.as_view())),
    url(r'(?P<base>[\w-]+)/kv/$', login_required(DjendBaseSettingsView.as_view())),
    url(r'(?P<base>[\w-]+)/kv/(?P<id>[\w-]+)/$', login_required(DjendBaseSettingsView.as_view())),
    url(r'(?P<base>[\w-]+)/create_exec/$', login_required(DjendExecSaveView.as_view())),
    #url(r'(?P<base>[\w-]+)/message/$', login_required(DjendMessageView.as_view())),
    url(r'(?P<base>[\w-]+)/exec/(?P<id>\w+)/$', \
                                            login_or_sharedkey(DjendExecView.as_view())),
    url(r'(?P<base>[\w-]+)/delete/(?P<id>\w+)/$', \
                                            login_required(DjendExecDeleteView.as_view())),
    url(r'(?P<base>[\w-]+)/clone/(?P<id>\w+)/$', \
                                            login_required(DjendExecCloneView.as_view())),
    url(r'(?P<base>[\w-]+)/static/(?P<name>[\w.-_]+)/', \
                                            login_or_sharedkey(DjendStaticView.as_view())),
    url(r'^$', DjendView.as_view())
)