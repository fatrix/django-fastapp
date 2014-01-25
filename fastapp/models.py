import urllib
from django.db import models
from django.contrib.auth.models import User
from django.template import Template
from django_extensions.db.fields import UUIDField
from fastapp.utils import Connection
import ConfigParser
import io
import StringIO


class AuthProfile(models.Model):
    user = models.OneToOneField(User, related_name="authprofile")
    access_token = models.CharField(max_length=72)


class Base(models.Model):
    name = models.CharField(max_length=32)
    uuid = UUIDField(auto=True)
    content = models.CharField(max_length=8192)
    user = models.ForeignKey(User, related_name='+', default=0, blank=True)

    @property
    def url(self):
        return "/fastapp/%s" % self.name

    @property
    def shared(self):
        return "/fastapp/%s/index/?shared_key=%s" % (self.name, urllib.quote(self.uuid))

    @property
    def config(self):
        config = ConfigParser.RawConfigParser()
        for texec in self.execs.all():
            config.add_section(texec.name)
            config.set(texec.name, 'module', texec.name+".py")
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
                module_content = connection.get_file("%s/%s" % (self.name, module_name))
                # save new exec
                app_exec_model, created = Exec.objects.get_or_create(base=self, name=name)
                app_exec_model.module = module_content
                app_exec_model.save()
                
            # delete old exec
            for local_exec in Exec.objects.filter(base=self).values('name'):
                if local_exec['name'] in config.sections():
                    print "exists"
                else:
                    Exec.objects.get(base=self, name=local_exec['name']).delete()


    def template(self, context):
        t = Template(self.content)
        return t.render(context)

    def __str__(self):
        return "<Base: %s>" % self.name

class Exec(models.Model):
    name = models.CharField(max_length=64)
    module = models.CharField(max_length=8192)
    base = models.ForeignKey(Base, related_name="execs", blank=True, null=True)

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Exec)
def synchronize_to_storage(sender, *args, **kwargs):
    instance = kwargs['instance']
    try:
        connection = Connection(instance.base.user.authprofile.access_token)
        connection.put_file("%s/%s.py" % (instance.base.name, instance.name), instance.module)
        if kwargs.get('created'):
            connection.put_file("%s/app.config" % (instance.base.name), instance.base.config)
    except Exception, e:
        print e

@receiver(post_delete, sender=Exec)
def synchronize_to_storage_on_delete(sender, *args, **kwargs):
    print "DELETE"
    instance = kwargs['instance']
    connection = Connection(instance.base.user.authprofile.access_token)
    print connection
    connection.put_file("%s/app.config" % (instance.base.name), instance.base.config)
    print connection.delete_file("%s/%s.py" % (instance.base.name, instance.name))
