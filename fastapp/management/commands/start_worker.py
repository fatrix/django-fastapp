import logging
import sys
import threading
from optparse import make_option

from django.core.management.base import BaseCommand

from fastapp.executors.remote import ExecutorServerThread
from fastapp.executors.heartbeat import HeartbeatThread, HEARTBEAT_QUEUE, update_status
from django.conf import settings


logger = logging.getLogger("fastapp.executors.remote")

class Command(BaseCommand):
    args = '<poll_id poll_id ...>'
    help = 'Closes the specified poll for voting'

    option_list = BaseCommand.option_list + (
        make_option('--username',
            action='store',
            dest='username',
            default=None,
            help='Username for the worker'),
        make_option('--password',
            action='store',
            dest='password',
            default=None,
            help='Password for the worker'),
        make_option('--base',
            action='store',
            dest='base',
            default=None,
            help='Base for the worker'),
        make_option('--vhost',
            action='store',
            dest='vhost',
            default=None,
            help='VHost on Queue system'),
        )

    def handle(self, *args, **options):
        threads = []

        base = options['base']
        vhost = options['vhost']
        username = options['username']
        # TODO: password should come from database
        password = options['password']
        #vhost = generate_vhost_configurationate_vhost_configuration(username, base)
        logger.info("vhost: %s" % vhost)

        for c in range(0, settings.FASTAPP_WORKER_THREADCOUNT):

            # start threads     
            #thread = ExecutorServerThread(c, "ExecutorServerThread-%s-%s" % (c, base), c, vhost, username, password)
            from fastapp.executors.remote import CONFIGURATION_QUEUE, RPC_QUEUE 
            name = "ExecutorSrvThread-%s-%s" % (c, base)
            thread = ExecutorServerThread(name, "localhost", vhost, 
                queues_consume=[[RPC_QUEUE]], 
                topic_receiver=[[CONFIGURATION_QUEUE]], 
                username=username, 
                password=password)
            threads.append(thread)
            thread.daemon = True
            thread.start()

        # increase thread_count by one because of HeartbeatThread
        thread_count = settings.FASTAPP_WORKER_THREADCOUNT+1
        update_status_thread = threading.Thread(target=update_status, args=[vhost, thread_count, threads])
        update_status_thread.daemon = True
        update_status_thread.start()        
        

        thread = HeartbeatThread("HeartbeatThread-%s" % c, "localhost", "/", 
            queues_produce=[[HEARTBEAT_QUEUE]],
            additional_payload={'vhost': vhost}
            )
        self.stdout.write('Start HeartbeatThread')
        threads.append(thread)
        thread.daemon = True
        thread.start()

        for t in threads:
            try:
                logger.info("%s Thread started" % settings.FASTAPP_WORKER_THREADCOUNT)
                t.join(1000)
            except KeyboardInterrupt:
                print "Ctrl-c received."
                sys.exit(0)