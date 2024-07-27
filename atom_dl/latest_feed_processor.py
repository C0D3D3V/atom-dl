import logging

from atom_dl.config_helper import Config
from atom_dl.feed_extractor import gen_extractors
from atom_dl.feed_updater import FeedUpdater
from atom_dl.job_creator import JobCreator
from atom_dl.types import AtomDlOpts
from atom_dl.utils import PathTools as PT
from atom_dl.utils import append_list_to_json, load_list_from_json


class LatestFeedProcessor:
    def __init__(
        self,
        opts: AtomDlOpts,
    ):
        self.opts = opts

    def process(self):
        all_feed_info_extractors = gen_extractors(self.opts)

        config = Config()
        storage_path = config.get_storage_path()

        path_of_last_feed_job_defs_json = PT.get_path_of_last_feed_job_defs_json()
        last_feed_job_definitions = load_list_from_json(path_of_last_feed_job_defs_json)

        job_creators = []
        for job_definition in last_feed_job_definitions:
            job_creators.append(JobCreator(job_definition, storage_path))

        if len(job_creators) == 0:
            logging.warning('No Jobs for last feed are defined')
            return

        logging.debug('Start collecting jobs...')
        jobs = []
        for extractor in all_feed_info_extractors:
            feed_updater = FeedUpdater(extractor)
            latest_feed = feed_updater.update()

            # Filter job creators based on feed name
            # We filter after the update, so that all feeds get an update
            feed_name = extractor.fie_key()
            valid_job_creators = []
            for job_creator in job_creators:
                if job_creator.can_handle_feed(feed_name):
                    valid_job_creators.append(job_creator)
            if len(valid_job_creators) == 0:
                continue

            for post in latest_feed:
                for job_creator in valid_job_creators:
                    job = job_creator.process(post, extractor)
                    if job is not None:
                        jobs.append(job)
                        # First job creator wins
                        break

        logging.info('Collected %d jobs', len(jobs))

        if len(jobs) == 0:
            return

        logging.info('Appending jobs to jobs queue...')
        path_of_jobs_json = PT.get_path_of_jobs_json()
        append_list_to_json(path_of_jobs_json, jobs)
        logging.info('Jobs appended to: %r', path_of_jobs_json)
