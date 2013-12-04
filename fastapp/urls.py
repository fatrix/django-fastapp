from django.conf.urls import include, patterns, url
from fastapp import views
from fastapp.views import my_login_required


urlpatterns = patterns('',

    url(r'dropbox_auth_start/?$',views.dropbox_auth_start),
    url(r'dropbox_auth_finish/?$',views.dropbox_auth_finish),

    #url(r'(?P<base>[\w-]+)/index/$', login_required(views.DjendBaseView.as_view(), login_url="/admin/")),
    #url(r'(?P<base>[\w-]+)/exec/(?P<id>\w+)/$', login_required(views.DjendExecView.as_view(), login_url="/admin/")),
    #url(r'(?P<base>[\w-]+)/static/(?P<name>[\w.-_]+)/', views.DjendStaticView.as_view()),
    #url(r'^$', login_required_or_accesskey(views.DjendBaseView.as_view(), login_url="/admin/")),
    url(r'(?P<base>[\w-]+)/index/$', my_login_required(views.DjendBaseView.as_view())),
    url(r'(?P<base>[\w-]+)/exec/(?P<id>\w+)/$', views.DjendExecView.as_view()),
    url(r'(?P<base>[\w-]+)/static/(?P<name>[\w.-_]+)/', views.DjendStaticView.as_view()),
    url(r'^$', views.DjendBaseView.as_view())
)