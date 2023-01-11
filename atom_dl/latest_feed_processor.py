from atom_dl.config_helper import Config
from atom_dl.feed_extractor import gen_extractors
from atom_dl.feed_updater import FeedUpdater
from atom_dl.job_creator import JobCreator
from atom_dl.jobs_worker import JobsWorker
from atom_dl.utils import Log


class LatestFeedProcessor:
    def __init__(
        self,
        verify_tls_certs: bool,
    ):
        self.verify_tls_certs = verify_tls_certs

    def process(self):
        all_feed_info_extractors = gen_extractors(self.verify_tls_certs)

        config = Config()
        last_feed_job_definitions = config.get_last_feed_job_definitions()
        storage_path = config.get_storage_path()

        job_creators = []
        for job_definition in last_feed_job_definitions:
            job_creators.append(JobCreator(job_definition, storage_path))

        Log.debug('Start collecting jobs...')
        jobs = []
        for extractor in all_feed_info_extractors:
            feed_updater = FeedUpdater(extractor)
            latest_feeds = feed_updater.update()

            # Filter job creators based on feed name
            feed_name = extractor.fie_key()
            valid_job_creators = []
            for job_creator in job_creators:
                if job_creator.can_handle_feed(feed_name):
                    valid_job_creators.append(job_creator)
            if len(valid_job_creators) == 0:
                continue

            for post in latest_feeds:
                for job_creator in valid_job_creators:
                    job = job_creator.process(post, extractor)
                    if job is not None:
                        jobs.append(job)
                        # First job creator wins
                        break

        Log.success('Collected all jobs')

        if len(jobs) == 0:
            return

        worker = JobsWorker()
        worker.handle_jobs(jobs)
