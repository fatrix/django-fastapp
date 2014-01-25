from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from fastapp.views import DjendBaseView, DjendBaseSaveView, DjendExecSaveView, DjendExecDeleteView, DjendExecView, DjendStaticView, \
                login_or_sharedkey, dropbox_auth_finish, dropbox_auth_start

urlpatterns = patterns('',

    url(r'dropbox_auth_start/?$',dropbox_auth_start),
    url(r'dropbox_auth_finish/?$',dropbox_auth_finish),

    url(r'(?P<base>[\w-]+)/index/$', login_or_sharedkey(DjendBaseView.as_view())),
    url(r'(?P<base>[\w-]+)/sync/$', login_required(DjendBaseSaveView.as_view())),
    url(r'(?P<base>[\w-]+)/create_exec/$', login_required(DjendExecSaveView.as_view())),
    #url(r'(?P<base>[\w-]+)/message/$', login_required(DjendMessageView.as_view())),
    url(r'(?P<base>[\w-]+)/exec/(?P<id>\w+)/$', \
                                            login_or_sharedkey(DjendExecView.as_view())),
    url(r'(?P<base>[\w-]+)/delete/(?P<id>\w+)/$', \
                                            login_required(DjendExecDeleteView.as_view())),
    url(r'(?P<base>[\w-]+)/static/(?P<name>[\w.-_]+)/', \
                                            login_or_sharedkey(DjendStaticView.as_view())),
    url(r'^$', login_or_sharedkey(DjendBaseView.as_view()))
)