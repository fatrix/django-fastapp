import logging 
import subprocess
import traceback
import sys
import urllib


logger = logging.getLogger(__name__)


def generate_vhost_configuration(*args):
    separator = "-"
    return "/"+separator.join(list(args))

def create_vhosts():
	print "create_vhosts"
	from models import Base 
    # create the vhosts, users and permissions
	for base in Base.objects.all():
		create_vhost(base)

def create_broker_url(username, password, host, port, vhost):
	return "amqp://%s:%s@%s:%s/%s" % (username, password, host, port, vhost)


def create_vhost(base):
    # create the vhosts, users and permissions
	from models import Base 
	vhost = generate_vhost_configuration(base.user.username, base.name)
	logger.info("Create vhost configuration: %s" % vhost)
	print "Create vhost configuration: %s" % vhost
	if sys.platform == "darwin":
		rabbitmqctl = "/usr/local/sbin/rabbitmqctl"
	else:
		rabbitmqctl = "sudo /usr/sbin/rabbitmqctl"
	try:
		print subprocess.Popen("%s add_vhost %s" % (rabbitmqctl, vhost), shell=True)
		print subprocess.Popen("%s add_user %s %s" % (rabbitmqctl, base.user.username, base.user.username), shell=True)
		print subprocess.Popen("%s set_permissions -p %s %s \"^.*\" \".*\" \".*\" " % (rabbitmqctl, vhost, base.user.username), shell=True)
	except Exception, e:
		traceback.print_exc()