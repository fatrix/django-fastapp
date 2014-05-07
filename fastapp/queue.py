import logging 
import pika
import sys
import subprocess
import traceback

logger = logging.getLogger(__name__)


def generate_vhost_configuration(*args):
    separator = "-"
    vhost = "/"+separator.join(list(args))
    logger.debug("generate_vhost_configuration: %s" % vhost)
    traceback.print_exc()
    return vhost

def create_vhosts():
	logger.info("create_vhosts")
	from models import Base 
    # create the vhosts, users and permissions
	for base in Base.objects.all():
		create_vhost(base)

def create_broker_url(username, password, host, port, vhost):
	return "amqp://%s:%s@%s:%s/%s" % (username, password, host, port, vhost)

def create_vhost(base):
    # create the vhosts, users and permissions
    vhost = base.executor.vhost
    logger.info("Create vhost configuration: %s" % vhost)
    if sys.platform == "darwin":
		rabbitmqctl = "/usr/local/sbin/rabbitmqctl"
    else:
		rabbitmqctl = "sudo /usr/sbin/rabbitmqctl"
    try:
		logger.info(subprocess.Popen("%s add_vhost %s" % (rabbitmqctl, vhost), shell=True))
		logger.info(subprocess.Popen("%s add_user %s %s" % (rabbitmqctl, base.name, base.executor.password), shell=True))
		logger.info(subprocess.Popen("%s set_permissions -p %s %s \"^.*\" \".*\" \".*\" " % (rabbitmqctl, vhost, base.name), shell=True))
    except Exception, e:
        logger.exception(e)
        raise e

def connect_to_queuemanager(host="localhost", vhost="/", username="guest", password="guest"):
    credentials = pika.PlainCredentials(username, password)
    logger.info("Trying to connect to: %s, %s, %s, %s" % (host, vhost, username, password))
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, virtual_host=vhost, heartbeat_interval=20, credentials=credentials))
    except Exception, e:
        logger.exception(e)
        raise e
    return connection

def connect_to_queue(host, queue, vhost="/", username="guest", password="guest"):
    logger.info("Connect to %s" % queue)
    try:
        #connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', virtual_host=vhost, heartbeat_interval=20))
        connection = connect_to_queuemanager(host, vhost, username, password)
        channel = connection.channel()
        #d = channel.queue_declare(queue, durable=True)
        d = channel.queue_declare(queue)
        logger.info(d.method)
        if d.method.__dict__['consumer_count']:
            logger.error("No consumer on queue %s" % queue)
    except Exception, e:
        logger.exception(e)
    return channel