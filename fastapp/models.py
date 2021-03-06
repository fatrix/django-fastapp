import urllib
import ConfigParser
import io
import subprocess
import os
import sys
import signal
import StringIO
import gevent
import json
import pytz
from datetime import datetime, timedelta

from django.db import models
from django.contrib.auth.models import User
from django.template import Template
from django_extensions.db.fields import UUIDField, ShortUUIDField
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
from django.db.transaction import commit_on_success
from django.conf import settings
from fastapp.queue import generate_vhost_configuration
from fastapp.executors.remote import distribute, CONFIGURATION_EVENT, SETTINGS_EVENT

from django.core import serializers

from fastapp.utils import Connection

import logging
logger = logging.getLogger(__name__)

index_template = """{% extends "fastapp/index.html" %}
{% block content %}
{% endblock %}
"""

class AuthProfile(models.Model):
    user = models.OneToOneField(User, related_name="authprofile")
    access_token = models.CharField(max_length=72)


class Base(models.Model):
    name = models.CharField(max_length=32)
    uuid = UUIDField(auto=True)
    content = models.CharField(max_length=16384, blank=True, default=index_template)
    user = models.ForeignKey(User, related_name='+', default=0, blank=True)
    public = models.BooleanField(default=False)

    @property
    def url(self):
        return "/fastapp/%s" % self.name

    @property
    def shared(self):
        print self.uuid
        return "/fastapp/%s/index/?shared_key=%s" % (self.name, urllib.quote(self.uuid))

    @property
    def config(self):
        config = ConfigParser.RawConfigParser()
        for texec in self.apys.all():
            config.add_section(texec.name)
            config.set(texec.name, 'module', texec.name+".py")
            config.set(texec.name, 'description', "\"%s\"" % texec.description)
        config_string = StringIO.StringIO()
        config.write(config_string)
        return config_string.getvalue()


    def refresh(self, put=False):
        from fastapp.utils import Connection, NotFound
        connection = Connection(self.user.authprofile.access_token)
        template_name = "%s/index.html" % self.name
        #if put:
        #    template_content = connection.put_file(template_name, self.content)
        #else:
        #    template_content = connection.get_file(template_name)
        #    self.content = template_content
        template_content = connection.get_file(template_name)
        self.content = template_content

    def refresh_execs(self, exec_name=None, put=False):
        from fastapp.utils import Connection, NotFound
        # execs
        connection = Connection(self.user.authprofile.access_token)
        app_config = "%s/app.config" % self.name
        config = ConfigParser.RawConfigParser()
        config.readfp(io.BytesIO(connection.get_file(app_config)))
        if put:
            if exec_name:
                connection.put_file("%s/%s.py" % (self.name, exec_name), self.execs.get(name=exec_name).module)
                connection.put_file(app_config, self.config)
            else:
                raise Exception("exec_name not specified")
        else:
            for name in config.sections():
                module_name = config.get(name, "module")
                try:
                    module_content = connection.get_file("%s/%s" % (self.name, module_name))
                except NotFound:
                    try:
                        Exec.objects.get(name=module_name, base=self).delete()                    
                    except Exec.DoesNotExist, e:
                        self.save()

                # save new exec
                app_exec_model, created = Apy.objects.get_or_create(base=self, name=name)
                app_exec_model.module = module_content
                app_exec_model.save()
                
            # delete old exec
            for local_exec in Apy.objects.filter(base=self).values('name'):
                if local_exec['name'] in config.sections():
                    logger.warn()
                else:
                    Apy.objects.get(base=self, name=local_exec['name']).delete()


    def template(self, context):
        t = Template(self.content)
        return t.render(context)

    @property
    def state(self):
        try:
            return self.executor.is_running()
        except IndexError, e:
            return False

    @property
    def pids(self):
        try:
            if self.executor.pid is None:
                return []
            return [self.executor.pid]
        except Exception, e:
            return []

    def start(self):
        return self.executor.start()

    def stop(self):
        return self.executor.stop()

    def __str__(self):
        return "<Base: %s>" % self.name

MODULE_DEFAULT_CONTENT = """def func(self):\n    pass"""


class Apy(models.Model):
    name = models.CharField(max_length=64)
    module = models.CharField(max_length=16384, default=MODULE_DEFAULT_CONTENT)
    base = models.ForeignKey(Base, related_name="apys", blank=True, null=True)
    description = models.CharField(max_length=1024, blank=True, null=True)

    def mark_executed(self):
        commit_on_success()

        self.counter.executed = F('executed')+1
        self.counter.save()

    def mark_failed(self):
        self.counter.failed = F('failed')+1
        self.counter.save()

    def get_exec_url(self):
        return "/fastapp/base/%s/exec/%s/?json=" % (self.base.name, self.name)

class Counter(models.Model):
    apy= models.OneToOneField(Apy, related_name="counter")
    executed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)


class Setting(models.Model):
    base = models.ForeignKey(Base, related_name="setting")
    key = models.CharField(max_length=128)
    value = models.CharField(max_length=8192)

class Instance(models.Model):
    is_alive = models.BooleanField(default=False)
    uuid = ShortUUIDField(auto=True)
    last_beat = models.DateTimeField(null=True, blank=True)
    executor = models.ForeignKey("Executor", related_name="instances")

    def mark_down(self):
        self.is_alive = False

        # restart
        #self.executor.start()

        self.save()

class Host(models.Model):
    name = models.CharField(max_length=50)



class Process(models.Model):
    running = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=64, null=True)

    def up(self):
        pass
        #logger.info("Heartbeat is up")

    def is_up(self):
        now = datetime.utcnow().replace(tzinfo = pytz.utc)
        delta = now - self.running
        return (delta < timedelta(seconds=10))


class Thread(models.Model):
    STARTED = "SA"
    STOPPED = "SO" 
    NOT_CONNECTED = "NC" 
    HEALTH_STATE_CHOICES = (
        (STARTED, "Started"),
        (STOPPED, "Stopped"),
        (NOT_CONNECTED, "Not connected")
        )

    name = models.CharField(max_length=64, null=True)
    parent = models.ForeignKey(Process, related_name="threads", blank=True, null=True)
    health = models.CharField(max_length=2, 
                            choices=HEALTH_STATE_CHOICES, 
                            default=STOPPED)

    def started(self):
        self.health = Thread.STARTED
        self.save()

    def not_connected(self):
        self.health = Thread.NOT_CONNECTED
        self.save()

class Executor(models.Model):
    base = models.OneToOneField(Base, related_name="executor")
    num_instances = models.IntegerField(default=1)
    pid = models.CharField(max_length=10, null=True)
    password = models.CharField(max_length=20, default=User.objects.make_random_password())
    started = models.BooleanField(default=False)
    #host = models.ForeignKey(Host)

    @property
    def vhost(self):
        return generate_vhost_configuration(self.base.user.username, self.base.name)

    def start(self):
        logger.info("Start manage.py start_worker")
        from queue import create_vhost
        create_vhost(self.base)

        try:
            Instance.objects.get(executor=self)
        except Instance.DoesNotExist, e:
            instance = Instance(executor=self)
            instance.save()
        
        python_path = sys.executable
        try:
            p = subprocess.Popen("%s %s/manage.py start_worker --settings=%s --vhost=%s --base=%s --username=%s --password=%s" % (
                    python_path, 
                    settings.PROJECT_ROOT,
                    settings.SETTINGS_MODULE,
                    self.vhost,
                    self.base.name, 
                    self.base.name, self.password),
                    cwd=settings.PROJECT_ROOT,
                    shell=True, stdin=None, stdout=None, stderr=None, preexec_fn=os.setsid
                )
            self.pid = p.pid
        except Exception, e:
            logger.exception(e)
            raise e
        logger.info("%s: worker started with pid %s" % (self, self.pid))
        self.started = True
        self.save()

    def stop(self):
        logger.info("kill process with PID %s" % self.pid)
        try:
            os.killpg(int(self.pid), signal.SIGTERM)
        except OSError, e:
            logger.exception(e)
        if not self.is_running():
            self.pid = None
            self.started = False
            self.save()

    def is_running(self):
        # if no pid, return directly false
        if not self.pid:
            return False

        # if pid, check
        return (subprocess.call("/bin/ps -ef|egrep -v grep|egrep -c %s 1>/dev/null" % self.pid, shell=True)==0)

    def is_alive(self):
        return self.instances.count()>1

    def __str__(self):
        return "Executor %s-%s" % (self.base.user.username, self.base.name)

@receiver(post_save, sender=Base)
def initialize_on_storage(sender, *args, **kwargs):
    instance = kwargs['instance']
    if not kwargs.get('created'): return
    try:
        connection = Connection(instance.user.authprofile.access_token)
        connection.create_folder("%s" % instance.name)
        connection.put_file("%s/app.config" % (instance.name), instance.config)
        
        connection.put_file("%s/index.html" % (instance.name), index_template)
    except Exception, e:
        logger.exception("error in initialize_on_storage")

@receiver(post_save, sender=Apy)
def synchronize_to_storage(sender, *args, **kwargs):
    instance = kwargs['instance']
    try:
        connection = Connection(instance.base.user.authprofile.access_token)
        gevent.spawn(connection.put_file("%s/%s.py" % (instance.base.name, instance.name), instance.module))
        if kwargs.get('created'):
            gevent.spawn(connection.put_file("%s/app.config" % (instance.base.name), instance.base.config))
    except Exception, e:
        logger.exception("error in synchronize_to_storage")

    if kwargs.get('created'):
        counter = Counter(apy=instance)
        counter.save()

    distribute(CONFIGURATION_EVENT, serializers.serialize("json", [instance,]), 
        generate_vhost_configuration(instance.base.user.username, instance.base.name), 
        instance.base.name, 
        instance.base.executor.password
    )

@receiver(post_save, sender=Setting)
def send_to_workers(sender, *args, **kwargs):
    instance = kwargs['instance']
    distribute(SETTINGS_EVENT, json.dumps({instance.key: instance.value}), 
        generate_vhost_configuration(instance.base.user.username, instance.base.name),
        instance.base.name, 
        instance.base.executor.password
    )

@receiver(post_save, sender=Base)
def synchronize_base_to_storage(sender, *args, **kwargs):
    instance = kwargs['instance']

    # create executor instance if none
    try:
        print instance.executor
    except Executor.DoesNotExist, e:
        logger.info("create executor")
        executor = Executor(base=instance)
        executor.save()
                

    #try:
    #    connection = Connection(instance.user.authprofile.access_token)
    #    gevent.spawn(connection.put_file("%s/index.html" % instance.name, instance.content))
    #except Exception, e:
    #    logger.exception("error in synchronize_base_to_storage")

@receiver(post_delete, sender=Base)
def base_to_storage_on_delete(sender, *args, **kwargs):
    instance = kwargs['instance']
    connection = Connection(instance.user.authprofile.access_token)
    try:
        gevent.spawn(connection.delete_file("%s" % instance.name))
    except Exception, e:
        logger.exception("error in base_to_storage_on_delete")

@receiver(post_delete, sender=Apy)
def synchronize_to_storage_on_delete(sender, *args, **kwargs):
    instance = kwargs['instance']
    from utils import NotFound
    try:
        connection = Connection(instance.base.user.authprofile.access_token)
        gevent.spawn(connection.put_file("%s/app.config" % (instance.base.name), instance.base.config))
        gevent.spawn(connection.delete_file("%s/%s.py" % (instance.base.name, instance.name)))
    except NotFound:
        logger.exception("error in synchronize_to_storage_on_delete")
    except Base.DoesNotExist:
        # if post_delete is triggered from base.delete()
        pass

