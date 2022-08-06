import time
import logging
import threading

from queue import Queue, Empty


class Downloader(threading.Thread):
    """
    Downloader processes the queue and puts an
    URL target back into the queue if an error occurs.
    """

    def __init__(
        self,
        queue: Queue,
        report: [],
        thread_id: int,
        queue_lock: threading.Lock,
        add_new_batch_callback,
        remove_everything_after_callback,
    ):
        """
        Initiates a downloader thread.
        """
        threading.Thread.__init__(self)
        self.daemon = True

        self.queue = queue
        self.report = report
        self.thread_id = thread_id
        self.queue_lock = queue_lock
        self.add_new_batch_callback = add_new_batch_callback
        self.remove_everything_after_callback = remove_everything_after_callback
        self.running = True
        self.waiting_for_items = False

    def run(self):
        """
        Work the queue until it is empty.
        """
        logging.debug('T%s - Downloader thread was started', self.thread_id)
        while self.running:
            try:
                # raise condition
                url_target = self.queue.get(False)
                self.waiting_for_items = False
            except Empty:
                self.waiting_for_items = True
                time.sleep(1)
                continue

            if not url_target.cancelled:
                response = url_target.download(self.thread_id)
                # All information is still saved in url_target

                # If a download fails, add it to the error report.
                if response is False:
                    logging.debug('T%s - URLTarget reports failure!', self.thread_id)
                    if url_target.last_one_of_category:
                        self.queue_lock.acquire()
                        self.remove_everything_after_callback(url_target.category, url_target.page_id)
                        self.queue_lock.release()
                    self.report['failure'].append(url_target)

                # If a download was successful, store it in the database.
                elif response is True:
                    logging.debug('T%s - URLTarget reports success!', self.thread_id)
                    if url_target.last_one_of_category:
                        self.queue_lock.acquire()
                        self.remove_everything_after_callback(url_target.category, url_target.page_id)
                        self.queue_lock.release()
                    else:
                        self.queue_lock.acquire()
                        self.add_new_batch_callback(url_target.category, url_target.page_id)
                        self.queue_lock.release()
                    self.report['success'].append(url_target)
            else:
                logging.debug('T%s - URLTarget cancelled!', self.thread_id)
                self.report['success'].append(url_target)

            self.queue.task_done()

        logging.debug('T%s - Downloader thread is finished', self.thread_id)
