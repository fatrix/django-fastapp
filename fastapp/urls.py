from django.conf.urls import patterns, url
from fastapp.views import DjendBaseView, DjendExecView, DjendStaticView, 
                login_or_sharedkey, dropbox_auth_finish, dropbox_auth_start

urlpatterns = patterns('',

    url(r'dropbox_auth_start/?$',dropbox_auth_start),
    url(r'dropbox_auth_finish/?$',dropbox_auth_finish),

    url(r'(?P<base>[\w-]+)/index/$', login_or_sharedkey(DjendBaseView.as_view())),
    url(r'(?P<base>[\w-]+)/exec/(?P<id>\w+)/$', 
                                            login_or_sharedkey(DjendExecView.as_view())),
    url(r'(?P<base>[\w-]+)/static/(?P<name>[\w.-_]+)/', 
                                            login_or_sharedkey(DjendStaticView.as_view())),
    url(r'^$', login_or_sharedkey(DjendBaseView.as_view()))
)