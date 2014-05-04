from django.core.management.base import BaseCommand
import logging
import sys
from optparse import make_option

from fastapp.executors.remote import ExecutorServerThread, HeartbeatThread
from fastapp.queue import generate_vhost_configuration
from fastapp.defaults import *

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
        )

    def handle(self, *args, **options):
        threads = []


        # generate config for worker
        #vhost = "/"
        #username = "guest"
        #password = "guest"

        base = options['base']
        username = options['username']
        password = options['password']
        vhost = generate_vhost_configuration(username, base)

        for c in range(1, FASTAPP_WORKER_THREADCOUNT):

            # start threads     
            thread = ExecutorServerThread(c, "ExecutorServerThread-%s-%s" % (c, base), c, vhost, username, password)
            self.stdout.write('Start ExecutorServerThread')
            threads.append(thread)
            thread.daemon = True
            thread.start()

        thread = HeartbeatThread(c, "HeartbeatThread-%s" % c, c, vhost)
        self.stdout.write('Start HeartbeatThread')
        threads.append(thread)
        thread.daemon = True
        thread.start()

        for t in threads:
            #print "join %s " % t
            try:
                logger.info("%s Thread started" % FASTAPP_WORKER_THREADCOUNT)
                t.join(1000)
            except KeyboardInterrupt:
                print "Ctrl-c received."
                sys.exit(0)