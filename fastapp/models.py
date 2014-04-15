import urllib
import ConfigParser
import io
import StringIO
import gevent
import json

from django.db import models
from django.contrib.auth.models import User
from django.template import Template
from django_extensions.db.fields import UUIDField
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
from django.db.transaction import commit_on_success
from fastapp.utils import Connection, NotFound
from fastapp.executors.remote import distribute, CONFIGURATION_QUEUE, SETTING_QUEUE

from django.core import serializers


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
    content = models.CharField(max_length=8192, blank=True, default=index_template)
    user = models.ForeignKey(User, related_name='+', default=0, blank=True)
    public = models.BooleanField(default=False)

    @property
    def url(self):
        return "/fastapp/%s" % self.name

    @property
    def shared(self):
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

    def __str__(self):
        return "<Base: %s>" % self.name

MODULE_DEFAULT_CONTENT = """def func(self):\n    pass"""


class Apy(models.Model):
    name = models.CharField(max_length=64)
    module = models.CharField(max_length=8192, default=MODULE_DEFAULT_CONTENT)
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
    executor = models.ForeignKey("Executor", related_name="instances")

class Host(models.Model):
    name = models.CharField(max_length=50)

class Executor(models.Model):
    user = models.ForeignKey(User, related_name="executor")
    num_instances = 1
    host = models.ForeignKey(Host)

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

    distribute(CONFIGURATION_QUEUE, serializers.serialize("json", [instance,]))

@receiver(post_save, sender=Setting)
def send_to_workers(sender, *args, **kwargs):
    instance = kwargs['instance']
    distribute(SETTING_QUEUE, json.dumps({
        instance.key: instance.value
        })
    )

@receiver(post_save, sender=Base)
def synchronize_base_to_storage(sender, *args, **kwargs):
    instance = kwargs['instance']
    try:
        connection = Connection(instance.user.authprofile.access_token)
        gevent.spawn(connection.put_file("%s/index.html" % instance.name, instance.content))
    except Exception, e:
        logger.exception("error in synchronize_base_to_storage")

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
    try:
        connection = Connection(instance.base.user.authprofile.access_token)
        gevent.spawn(connection.put_file("%s/app.config" % (instance.base.name), instance.base.config))
        gevent.spawn(connection.delete_file("%s/%s.py" % (instance.base.name, instance.name)))
    except NotFound, e:
        logger.exception("error in synchronize_to_storage_on_delete")
    except Base.DoesNotExist, e:
        # if post_delete is triggered from base.delete()
        pass

