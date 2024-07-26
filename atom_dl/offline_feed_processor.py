import logging

from atom_dl.config_helper import Config
from atom_dl.feed_extractor import gen_extractors
from atom_dl.job_creator import JobCreator
from atom_dl.types import AtomDlOpts
from atom_dl.utils import PathTools as PT
from atom_dl.utils import append_list_to_json, load_list_from_json


class OfflineFeedProcessor:
    def __init__(
        self,
        opts: AtomDlOpts,
    ):
        self.opts = opts
        self.path_to_job_defs = PT.get_abs_path(opts.path_to_job_defs)

    def process(self):
        all_feed_info_extractors = gen_extractors(self.opts)

        config = Config()
        storage_path = config.get_storage_path()

        last_feed_job_definitions = load_list_from_json(self.path_to_job_defs)

        job_creators = []
        for job_definition in last_feed_job_definitions:
            job_creators.append(JobCreator(job_definition, storage_path))

        if len(job_creators) == 0:
            logging.warning('No Jobs for offline feed are defined')
            return

        logging.debug('Start collecting jobs...')
        jobs = []
        for extractor in all_feed_info_extractors:
            # Filter job creators based on feed name
            feed_name = extractor.fie_key()
            valid_job_creators = []
            for job_creator in job_creators:
                if job_creator.can_handle_feed(feed_name):
                    valid_job_creators.append(job_creator)
            if len(valid_job_creators) == 0:
                continue

            path_of_feed_json = PT.get_path_of_feed_json(feed_name)
            offline_feed = load_list_from_json(path_of_feed_json)

            for post in offline_feed:
                for job_creator in valid_job_creators:
                    job = job_creator.process(post, extractor)
                    if job is not None:
                        jobs.append(job)
                        # First job creator wins
                        break

        logging.info('Collected all jobs')

        if len(jobs) == 0:
            return

        logging.info('Appending jobs to jobs queue...')
        path_of_jobs_json = PT.get_path_of_jobs_json()
        append_list_to_json(path_of_jobs_json, jobs)
        logging.info('Jobs appended to: %r', path_of_jobs_json)
