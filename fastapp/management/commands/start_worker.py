from django.core.management.base import BaseCommand
import logging
import sys

from fastapp.executors.remote import ExecutorServerThread

logger = logging.getLogger("fastapp.executors.remote")

class Command(BaseCommand):
    args = '<poll_id poll_id ...>'
    help = 'Closes the specified poll for voting'


    def handle(self, *args, **options):
        THREAD_COUNT = 10
        threads = []
        for c in range(1, THREAD_COUNT):
                thread = ExecutorServerThread(c, "ExecutorServerThread-%s" % c, c)
                self.stdout.write('Start ExecutorServerThread')
                threads.append(thread)
                thread.daemon = True
                thread.start()

        for t in threads:
            #print "join %s " % t
            try:
                logger.info("%s Thread started" % THREAD_COUNT)
                t.join(1000)
            except KeyboardInterrupt:
                print "Ctrl-c received."
                sys.exit(0)