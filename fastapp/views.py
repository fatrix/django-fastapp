import logging
import traceback
import json
import datetime
import copy
import pusher

from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.template.loader import render_to_string
from django.views.generic import View
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseNotFound, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden
from django.views.generic.base import ContextMixin
from django.conf import settings
import dropbox
from dropbox.rest import ErrorResponse
from fastapp.utils import message

from utils import UnAuthorized, Connection, NoBasesFound
from fastapp.models import AuthProfile, Base

class DjendStaticView(View):

    def get(self, request, *args, **kwargs):
        static_path = "%s/%s/%s" % (kwargs['base'], "static", kwargs['name'])
        try:

            base_model = Base.objects.get(name=kwargs['base'])
            auth_token = base_model.user.authprofile.access_token
            client = dropbox.client.DropboxClient(auth_token)
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
        return Connection(request.user.authprofile.access_token)


class DjendExecView(View, DjendMixin):
    STATE_OK = "OK"
    STATE_NOK = "NOK"


    def _do(self, sfunc, do_kwargs):
        exception = None;  returned = None
        status = self.STATE_OK

        func = None 

        request = do_kwargs['request']
        username = copy.copy(do_kwargs['request'].user.username)

        # debug incoming request
        #from pprint import pprint
        #pprint(request)
        if request.method == "GET":
            query_string = copy.copy(request.GET)
        else:
            query_string = copy.copy(request.POST)
        query_string.pop('json')

        debug(username, "%s-Request received, URI %s?%s " % (request.method, request.path, query_string.urlencode()))

        try:

            exec sfunc
            func.username=username
            func.request=do_kwargs['request']
            func.session=do_kwargs['request'].session
            func.info=info
            func.GET=copy.deepcopy(request.GET)
            func.POST=copy.deepcopy(request.POST)
            func.debug=debug
            func.warn=warn
            func.error=error

            returned = func(func)
        except Exception, e:
            exception = "%s: %s" % (type(e).__name__, e.message)
            traceback.print_exc()
            status = self.STATE_NOK
        return {'status': status, 'returned': returned, 'exception': exception}

    def get(self, request, *args, **kwargs):
        base = kwargs['base']
        exec_id = kwargs['id']
        base_model = Base.objects.get(name=base)
        exec_model = base_model.execs.get(name=exec_id)

        do_kwargs = {'request': request}
        data = self._do(exec_model.module, do_kwargs)
        data.update({'id': kwargs['id']})

        if request.GET.has_key('json'):
            if data['status'] == "OK":
                user_message(logging.INFO, request.user.username, str(data))
            elif data['status'] == "NOK":
                user_message(logging.ERROR, request.user.username, str(data))
            if isinstance(data['returned'], HttpResponseRedirect):
                #return data
                location = data['returned']['Location']
                user_message(logging.INFO, request.user.username, "Redirect to: %s" % location)
                return HttpResponse(json.dumps(data['returned']['Location']), content_type="application/json")
            else:
                return HttpResponse(json.dumps(data), content_type="application/json")

        return HttpResponseRedirect("/fastapp/%s/index/?done=%s" % (base, exec_id))


class DjendSharedView(View, ContextMixin):

    def get(self, request, *args, **kwargs):
        context = RequestContext(request)
        base_name = kwargs.get('base')
        shared_key = request.GET.get('shared_key')

        if not shared_key:
            shared_key = request.session.get('shared_key')

        base_model = get_object_or_404(Base, name=base_name, uuid=shared_key)
        # store it in session list
        if not request.session.__contains__('shared_bases'):
            request.session['shared_bases'] = {}
        request.session['shared_bases'][base_name] = shared_key
        request.session.modified = True

        # context
        context['shared_bases'] = request.session['shared_bases']
        context['FASTAPP_EXECS'] = base_model.execs.all().order_by('name')
        context['LAST_EXEC'] = request.GET.get('done')
        context['active_base'] = base_model
        context['FASTAPP_NAME'] = base_model.name
        context['DROPBOX_REDIRECT_URL'] = settings.DROPBOX_REDIRECT_URL
        context['PUSHER_KEY'] = settings.PUSHER_KEY
        context['FASTAPP_STATIC_URL'] = "/%s/%s/static/" % ("fastapp", base_model.name)

        rs = base_model.template(context)
        return HttpResponse(rs)

class DjendBaseSaveView(View):

    def post(self, request, *args, **kwargs):
        base = get_object_or_404(Base, name=kwargs['base'], user=User.objects.get(username=request.user.username))
        content = request.POST.get('content', None)

        # syncing to storage provider
        # exec
        if request.POST.has_key('exec_name'):
            exec_name = request.POST.get('exec_name')
            # save in database
            e = base.execs.get(name=exec_name)
            e.module = content
            e.save()
            info(request.user.username, "Saved")
            base.refresh_execs(exec_name, put=True)
            info(request.user.username, "Synced '%s' to Dropbox" % exec_name)
        # base
        else:
            base.content = content
            base.save()
            # save in database
            info(request.user.username, "Saved")
            base.refresh(put=True)
            info(request.user.username, "Synced '%s' to Dropbox" % base.name)

        return HttpResponse()

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(DjendBaseSaveView, self).dispatch(*args, **kwargs)

class DjendBaseView(View, ContextMixin):

    def _refresh_bases(self, username):
        connection = Connection(AuthProfile.objects.get(user__username=username).access_token)
        bases = connection.listing()
        for remote_base in bases:
            remote_base, created = Base.objects.get_or_create(name=remote_base, user=User.objects.get(username=username))
            remote_base.save()

        refreshed_bases = []
        for base in Base.objects.filter(user__username=username):
            if base.name in bases:
                logging.debug("refresh base '%s'" % base)
                try:
                    base.refresh()
                    base.refresh_execs()
                    base.save()
                except Exception, e:
                    print traceback.format_exc()

                refreshed_bases.append(base)
            else:
                base.delete()

        return refreshed_bases

    def _refresh_single_base(self, base):
        base = Base.objects.get(name=base)
        base.refresh()
        base.save()

    def get(self, request, *args, **kwargs):
        rs = None
        context = RequestContext(request)

        # redirect to shared view
        if not request.user.is_authenticated():
            if request.GET.has_key('shared_key') or request.session.__contains__("shared_key"):
                return DjendSharedView.as_view()(request, *args, **kwargs)

        try:
            # refresh bases from dropbox
            refresh = "refresh" in request.GET

            base = kwargs.get('base')

            #if request.session.get('bases') is None or refresh:
            if refresh and base:
                self._refresh_single_base(base)
            elif refresh:
                self._refresh_bases(request.user.username)
                return HttpResponseRedirect("/fastapp/")

            base_model = None
            if base:
                base_model = get_object_or_404(Base, name=base, user=request.user.id)
                base_model.save()

                # execs
                try:
                    context['FASTAPP_EXECS'] = base_model.execs.all().order_by('name')
                except ErrorResponse, e:
                    messages.warning(request, "No app.json found", extra_tags="alert-warning")
                    logging.debug(e)

            # context
            try:
                context['bases'] = Base.objects.filter(user=request.user.id).order_by('name')
                if base is not None:
                    context['FASTAPP_NAME'] = base
                    context['DROPBOX_REDIRECT_URL'] = settings.DROPBOX_REDIRECT_URL
                    context['PUSHER_KEY'] = settings.PUSHER_KEY
                    context['FASTAPP_STATIC_URL'] = "/%s/%s/static/" % ("fastapp", base)
                    context['active_base'] = base_model
                    context['LAST_EXEC'] = request.GET.get('done')
                    rs = base_model.template(context)
                else:
                    template_name = "fastapp/index.html"
                    rs = render_to_string(template_name, context_instance=context)

            except ErrorResponse, e:
                if e.__dict__['status'] == 404:
                    logging.debug(base)
                    logging.debug("Template not found")
                    messages.error(request, "Template %s not found" % template_name, extra_tags="alert-danger")

        # error handling
        except (UnAuthorized, AuthProfile.DoesNotExist), e:
            print traceback.format_exc()
            return HttpResponseRedirect("/fastapp/dropbox_auth_start")
        except NoBasesFound, e:
            print traceback.format_exc()
            message(request, logging.WARNING, "No bases found")
        #except Exception, e:
        #    print traceback.format_exc()
        #    return HttpResponseServerError()

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


def login_or_sharedkey(function):
    def wrapper(request, *args, **kwargs):
        user=request.user
        # if logged in
        if user.is_authenticated():
            return function(request, *args, **kwargs)
        # if shared key in query string
        if request.GET.has_key('shared_key'):
            shared_key = request.GET.get('shared_key')
            base_name = kwargs.get('base')
            get_object_or_404(Base, name=base_name, uuid=shared_key)
            request.session['shared_key'] = shared_key
            return function(request, *args, **kwargs)
        # if shared key in session
        if request.session.__contains__('shared_key'):
            return function(request, *args, **kwargs)
        return HttpResponseRedirect("/admin/")
    return wrapper

def user_message(level, username, message):

    p = pusher.Pusher(
      app_id=settings.PUSHER_APP_ID,
      key=settings.PUSHER_KEY,
      secret=settings.PUSHER_SECRET
    )
    now = datetime.datetime.now()
    if level == logging.INFO:
        class_level = "info"        
    elif level == logging.DEBUG:
        class_level = "debug"        
    elif level == logging.WARNING:
        class_level = "warn"        
    elif level == logging.ERROR:
        class_level = "error"        

    p[username].trigger('console_msg', {'datetime': str(now), 'message': str(message), 'class': class_level})

def info(username, gmessage): 
        return user_message(logging.INFO, username, gmessage)
def debug(username, gmessage): 
        return user_message(logging.DEBUG, username, gmessage)
def error(username, gmessage): 
        return user_message(logging.ERROR, username, gmessage)
def warn(username, gmessage): 
        return user_message(logging.WARN, username, gmessage)
