import logging
import json
import datetime

from django.contrib import messages
from django.shortcuts import render_to_response
from django.template import TemplateDoesNotExist, RequestContext, Template
from django.template.loader import render_to_string
from django.views.generic import View
from django.http import *
from django.views.generic.base import ContextMixin
from django.conf import settings
import dropbox
from dropbox.rest import ErrorResponse

from utils import UnAuthorized, Connection, NoBasesFound
from fastapp.models import AuthProfile


class DjendStaticView(View):

    def get(self, request, *args, **kwargs):
        static_path = "%s/%s/%s" % (kwargs['base'], "static", kwargs['name'])
        try:
            auth_profile, created = AuthProfile.objects.get_or_create(user=request.user)
            if created:
                auth_profile.save()
                return HttpResponseRedirect("/fastapp/dropbox_auth_start")

            client = dropbox.client.DropboxClient(auth_profile.access_token)
            f = client.get_file(static_path).read()

            # default
            mimetype = "text/plain"
            if static_path.endswith('.js'):
                mimetype = "text/javascript"
            if static_path.endswith('.css'):
                mimetype = "text/css"
            if static_path.endswith('.png'):
                mimetype = "image/png"
            return HttpResponse(f, mimetype=mimetype)
        except ErrorResponse, e:
            return HttpResponseNotFound("Not found: "+static_path)


class DjendMixin(object):

    def connection(self, request):
        return Connection(request.user.username)


class DjendExecView(View, DjendMixin):
    STATE_OK = "OK"
    STATE_NOK = "ERROR"

    def _do(self, sfunc, do_kwargs):
        func = None;  exception = None;  returned = None
        status = self.STATE_OK

        exec sfunc

        try:
            returned = func(**do_kwargs)
        except Exception, e:
            exception = "%s: %s" % (type(e).__name__, e.message)
            status = self.STATE_NOK
        return {'status': status, 'returned': returned, 'exception': exception}

    def get(self, request, *args, **kwargs):
        base = kwargs['base']

        connection = self.connection(request)

        base_config = json.loads(connection.get_file(base+"/app.json"))
        py_name = base_config[kwargs['id']]
        py_module = connection.get_file(base+"/"+py_name)
        do_kwargs = {'request': request}
        data = self._do(py_module, do_kwargs)
        data.update({'id': kwargs['id']})

        if data['status'] == self.STATE_NOK:
            message(request, logging.ERROR, data)
        else:
            message(request, logging.INFO, data)
        if isinstance(data['returned'], HttpResponseRedirect):
            return data['returned']
        return HttpResponseRedirect("/fastapp/%s/index/" % base)


def message(request, level, message):
    dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if level == logging.ERROR:
        tag = "alert-danger"
    elif level == logging.INFO:
        tag = "alert-info"
    elif level == logging.WARN:
        tag = "alert-info"
    messages.error(request, dt + " " + str(message)[:1000], extra_tags="%s safe" % tag)


class DjendBaseView(View, ContextMixin):

    def get(self, request, *args, **kwargs):
        rs = None
        context = RequestContext(request)

        try:
            connection = Connection(request.user.username)

            # bases
            refresh = "refresh" in request.GET
            if request.session.get('bases') is None or refresh:
                request.session['bases'] = connection.listing()
            if refresh:
                return HttpResponseRedirect("/fastapp/")

            # base and config (app.json)
            base = kwargs.get('base')
            base_config = {}
            if base:
                try:
                    request.session['base_config'] = json.loads(connection.get_file(base+"/app.json"))
                except ErrorResponse, e:
                    messages.warning(request, "No %s/app.json found" % base, extra_tags="alert-warning")
                    logging.debug(e)
                base_config = request.session['base_config']

            try:
                context['DJEND_EXECS'] = base_config.keys()
            except ErrorResponse, e:
                messages.warning(request, "No app.json found", extra_tags="alert-warning")
                logging.debug(e)
            try:
                context['bases'] = request.session['bases']
                context['FASTAPP_NAME'] = base

                if base is not None:
                    context['FASTAPP_STATIC_URL'] = "/%s/%s/static/" % ("fastapp", base)

                if base is None:
                    template_name = "fastapp/index.html"
                    rs = render_to_string(template_name, context_instance=context)
                else:
                    template_name = "%s/index.html" % base
                    templ = connection.get_file(template_name)
                    t = Template(templ)
                    rs = t.render(context)

            except ErrorResponse, e:
                if e.__dict__['status'] == 404:
                    logging.debug(base)
                    logging.debug("Template not found")
                    messages.error(request, "Template %s not found" % template_name, extra_tags="alert-danger")

        except (UnAuthorized, AuthProfile.DoesNotExist), e:
            print e
            return HttpResponseRedirect("/fastapp/dropbox_auth_start")
        except NoBasesFound, e:
            print e
            message(request, logging.WARNING, "No bases found")
        except Exception, e:
            print e
            return HttpResponseServerError()

        if not rs:
            rs = render_to_string("fastapp/index.html", context_instance=context)

        return HttpResponse(rs)


def get_dropbox_auth_flow(web_app_session):
    redirect_uri = "%s/fastapp/dropbox_auth_finish" % settings.DROPBOX_REDIRECT_URL
    dropbox_consumer_key = settings.DROPBOX_CONSUMER_KEY
    dropbox_consumer_secret = settings.DROPBOX_CONSUMER_SECRET
    return dropbox.client.DropboxOAuth2Flow(dropbox_consumer_key, dropbox_consumer_secret, redirect_uri, web_app_session, "dropbox-auth-csrf-token")


# URL handler for /dropbox-auth-start
def dropbox_auth_start(request):
    authorize_url = get_dropbox_auth_flow(request.session).start()
    return HttpResponseRedirect(authorize_url)


# URL handler for /dropbox-auth-finish
def dropbox_auth_finish(request):
    try:
        access_token, user_id, url_state = get_dropbox_auth_flow(request.session).finish(request.GET)
        auth, created = AuthProfile.objects.get_or_create(user=request.user)
        # store access_token
        auth.access_token = access_token
        auth.user = request.user
        auth.save()

        return HttpResponseRedirect("/fastapp/")
    except dropbox.client.DropboxOAuth2Flow.BadRequestException, e:
        return HttpResponseBadRequest(e)
    except dropbox.client.DropboxOAuth2Flow.BadStateException, e:
        # Start the auth flow again.
        return HttpResponseRedirect("http://www.mydomain.com/dropbox_auth_start")
    except dropbox.client.DropboxOAuth2Flow.CsrfException, e:
        return HttpResponseForbidden()
    except dropbox.client.DropboxOAuth2Flow.NotApprovedException, e:
        raise e
    except dropbox.client.DropboxOAuth2Flow.ProviderException, e:
        raise e

