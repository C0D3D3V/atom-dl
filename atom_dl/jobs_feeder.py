import asyncio
import bisect
import logging
import os
import sys
import traceback
from itertools import cycle

from atom_dl.config_helper import Config
from atom_dl.my_jd_api import MyJdApi, MYJDException
from atom_dl.utils import PathTools as PT
from atom_dl.utils import append_list_to_json, load_list_from_json, write_to_json


class JobsFeeder:
    def __init__(self, do_not_auto_start_downloading: bool):
        self.do_not_auto_start_downloading = do_not_auto_start_downloading

        self.finished = False
        self.num_jobs_total = 0
        self.done_links = []
        self.new_jobs = []
        self.max_parallel_decrypt_jobs = 15
        self.decrypt_jobs = []
        self.decrypted_jobs = []
        self.urls_jobs = []
        self.filenames_jobs = []
        self.checked_jobs = []

        config = Config()
        self.auto_start_downloading = config.get_auto_start_downloading()

        logging.info("Try to connect to MyJDownloader...")
        try:
            my_jd_username = config.get_my_jd_username()
            my_jd_password = config.get_my_jd_password()
            my_jd_device = config.get_my_jd_device()
        except ValueError as config_error:
            logging.error(str(config_error))
            logging.error(
                "Please set all MyJDownloader settings in your configuration:\n"
                + "{my_jd_username, my_jd_password, my_jd_device}"
            )
            sys.exit(-1)
        self.jd = MyJdApi()
        self.jd_device = None
        try:
            self.jd.set_app_key("Atom-Downloader")
            self.jd.connect(my_jd_username, my_jd_password)
            self.jd_device = self.jd.get_device(my_jd_device)
        except MYJDException as jd_error:
            logging.error(str(jd_error).strip())
            logging.error("Error no connection could be established with MyJDownloader.")
            sys.exit(-2)

    def __del__(self):
        try:
            self.jd.disconnect()
        except MYJDException as jd_error:
            logging.error(str(jd_error).strip())

    def process(self):
        logging.debug('Start working on jobs...')
        jobs_json_file_path = PT.get_path_of_jobs_json()
        self.new_jobs = load_list_from_json(jobs_json_file_path)

        done_links_json_file_path = PT.get_path_of_done_links_json()
        self.done_links = load_list_from_json(done_links_json_file_path)
        # To make the search for elements faster we sort the list
        self.done_links.sort()

        self.num_jobs_total = len(self.new_jobs)
        if self.num_jobs_total > 0:
            asyncio.run(self.jd_job_chain())

    async def jd_job_chain(self):
        gather_jobs = asyncio.gather(
            *[
                self.send_jobs_to_jd(),
                self.check_decrypt_jobs(),
                self.check_decrypted_jobs(),
                self.check_urls_jobs(),
                self.check_filenames_jobs(),
                self.check_finish_condition(),
            ]
        )
        try:
            await gather_jobs
        except Exception:
            traceback.print_exc()
            gather_jobs.cancel()
            sys.exit(1)

        append_list_to_json(PT.get_path_of_checked_jobs_json(), self.checked_jobs)
        self.save_all_done_links()
        self.delete_or_backup_done_jobs()

        if self.auto_start_downloading and not self.do_not_auto_start_downloading:
            self.start_downloads()
        else:
            logging.info("Skipping auto downloading")

    def start_downloads(self):
        link_ids = []
        for checked_job in self.checked_jobs:
            decrypted_links = checked_job.get('decrypted_links', [])
            for decrypted_link in decrypted_links:
                link_id = decrypted_link.get('uuid', None)
                availability = decrypted_link.get('availability', 'OFFLINE')
                is_already_done = decrypted_link.get('is_already_done', False)
                if link_id is not None and not is_already_done and availability == 'ONLINE':
                    link_ids.append(link_id)

        self.jd_device.linkgrabber.move_to_downloadlist(link_ids, [])

        start_result = self.jd_device.downloadcontroller.start_downloads()
        if not start_result:
            logging.warning('JDownloader did not start automatically!')
        else:
            logging.info('JDownloader is starting downloading...')

    def save_all_done_links(self):
        # Extract all decrypted links from checked_jobs
        all_decrypted_links = []
        for checked_job in self.checked_jobs:
            decrypted_links = checked_job.get('decrypted_links', [])
            for decrypted_link in decrypted_links:
                url = decrypted_link.get('url', None)
                availability = decrypted_link.get('availability', 'OFFLINE')
                is_already_done = decrypted_link.get('is_already_done', False)
                if url is not None and not is_already_done and availability in ['ONLINE', 'OFFLINE']:
                    all_decrypted_links.append(url)

        # Items should be unique since we already tested if they are in the list
        self.done_links.extend(all_decrypted_links)
        self.done_links.sort()
        path_of_done_links_json = PT.get_path_of_done_links_json()
        write_to_json(path_of_done_links_json, self.done_links)
        logging.info('Checked jobs appended to: %r', path_of_done_links_json)

    def delete_or_backup_done_jobs(self):
        # Handle old jobs json
        num_checked_jobs = len(self.checked_jobs)
        json_old_jobs_file_path = PT.get_path_of_jobs_json()
        if not os.path.isfile(json_old_jobs_file_path):
            logging.warning('Warning: Could not find old jobs file %r', json_old_jobs_file_path)

        if num_checked_jobs != self.num_jobs_total:
            # Move jobs file to backup location
            logging.warning('Warning: Only done %d out of %d jobs', num_checked_jobs, self.num_jobs_total)
            json_backup_jobs_file_path = PT.get_path_of_backup_jobs_json()
            if os.path.isfile(json_old_jobs_file_path):
                try:
                    os.rename(json_old_jobs_file_path, json_backup_jobs_file_path)
                except OSError as err:
                    logging.warning(
                        'Warning: Could not backup old jobs file %r Error: %s', json_old_jobs_file_path, err
                    )
        else:
            # Remove old jobs file
            if os.path.isfile(json_old_jobs_file_path):
                try:
                    os.remove(json_old_jobs_file_path)
                except OSError as err:
                    logging.warning(
                        'Warning: Could not delete old jobs file %r Error: %s', json_old_jobs_file_path, err
                    )

    async def check_finish_condition(self):
        spinner = cycle('/|\\-')
        while True:
            if (
                len(self.new_jobs) == 0
                and len(self.decrypt_jobs) == 0
                and len(self.decrypted_jobs) == 0
                and len(self.urls_jobs) == 0
                and len(self.filenames_jobs) == 0
            ):
                self.finished = True
                logging.info('\n All Jobs Done')
                return
            print(
                f"\r\033[KDone: {len(self.checked_jobs):04} / {self.num_jobs_total:04} Jobs {next(spinner)}",
                end='',
            )
            await asyncio.sleep(1)

    async def send_jobs_to_jd(self):
        while not self.finished:
            if len(self.new_jobs) > 0 and len(self.decrypt_jobs) < self.max_parallel_decrypt_jobs:
                next_job = self.new_jobs.pop(0)
                add_querry = {
                    "assignJobID": True,
                    # "autoExtract": False,
                    "autostart": False,
                    # "dataURLs": [],
                    # "deepDecrypt": False,
                    "destinationFolder": next_job.get('destination_path', ''),
                    "downloadPassword": next_job.get('password', ''),
                    "extractPassword": next_job.get('password', ''),
                    "links": "\n".join(next_job.get('download_links', [])),
                    "overwritePackagizerRules": True,
                    "packageName": next_job.get('package_name', ''),
                    "priority": 'DEFAULT',
                    "sourceUrl": '',
                }
                result = self.jd_device.linkgrabber.add_links(add_querry)
                next_job['crawl_job_id'] = result.get('id', None)
                # Add job to queue to check if decryption finished
                self.decrypt_jobs.append(next_job)
                await asyncio.sleep(0)
            else:
                await asyncio.sleep(1)

    async def check_decrypt_jobs(self):
        while not self.finished:
            if len(self.decrypt_jobs) > 0:
                jobIds = []
                for decrypt_job in self.decrypt_jobs:
                    job_id = decrypt_job.get('crawl_job_id', None)
                    if job_id is not None:
                        jobIds.append(job_id)
                status_querry = {
                    "collectorInfo": True,
                    "jobIds": jobIds,
                }
                result = self.jd_device.linkgrabber.query_link_crawler_jobs(status_querry)

                for jobId in jobIds:
                    found = False
                    job_status_crawling = True
                    job_status_checking = True
                    for job_status in result:
                        job_status_id = job_status.get('jobId', None)
                        if job_status_id is None:
                            continue  # should not happen
                        if job_status_id == jobId:
                            found = True
                            job_status_crawling = job_status.get('crawling', False)
                            job_status_checking = job_status.get('checking', False)
                            break
                    # We assume the job is finished if it was not found
                    if not found or (not job_status_crawling and not job_status_checking):
                        job_idx = None
                        for idx, decrypt_job in enumerate(self.decrypt_jobs):
                            job_id = decrypt_job.get('crawl_job_id', None)
                            if job_id is None:
                                continue  # should not happen
                            if job_id == jobId:
                                job_idx = idx
                                break
                        if job_idx is not None:
                            decrypted_job = self.decrypt_jobs.pop(job_idx)
                            # Add job to queue to check result of decryption
                            self.decrypted_jobs.append(decrypted_job)

            await asyncio.sleep(1)

    async def check_decrypted_jobs(self):
        while not self.finished:
            if len(self.decrypted_jobs) > 0:
                next_decrypted_job = self.decrypted_jobs.pop(0)

                job_id = next_decrypted_job.get('crawl_job_id', None)
                if job_id is None:
                    await asyncio.sleep(0)
                    continue  # should not happen
                jobIds = [job_id]
                link_querry = {
                    "availability": True,
                    "bytesTotal": True,
                    "comment": False,
                    "enabled": False,
                    "host": True,
                    "jobUUIDs": jobIds,
                    "maxResults": -1,
                    "packageUUIDs": [],
                    "password": False,
                    "priority": False,
                    "startAt": 0,
                    "status": True,
                    "url": True,
                    "variantID": False,
                    "variantIcon": False,
                    "variantName": False,
                    "variants": False,
                }
                decrypted_links = self.jd_device.linkgrabber.query_links(link_querry)

                next_decrypted_job['decrypted_links'] = decrypted_links
                self.urls_jobs.append(next_decrypted_job)

                await asyncio.sleep(0)
            else:
                await asyncio.sleep(1)

    def check_already_done(self, url: str) -> bool:
        """
        Return True if the URL is already done
        """
        idx = bisect.bisect_left(self.done_links, url)
        return idx != len(self.done_links) and self.done_links[idx] == url

    async def check_urls_jobs(self):
        while not self.finished:
            if len(self.urls_jobs) > 0:
                next_retry_job = self.urls_jobs.pop(0)

                decrypted_links = next_retry_job.get('decrypted_links', [])
                retry_counter = next_retry_job.get('retry', 0)

                # Check online status of URLs nd Package
                is_online = False
                is_offline = False
                is_already_done = False
                needs_retry = False
                remove_links_ids = []
                for decrypted_link in decrypted_links:
                    availability = decrypted_link.get('availability', 'OFFLINE')
                    url = decrypted_link.get('url', None)
                    decrypted_link_id = decrypted_link.get('uuid', None)
                    if url is None or decrypted_link_id is None:
                        continue  # should not happen
                    already_done = self.check_already_done(url)
                    if already_done:
                        is_already_done = True
                        decrypted_link['is_already_done'] = True
                        remove_links_ids.append(decrypted_link_id)
                    elif availability == 'ONLINE':
                        is_online = True
                    elif availability in ['TEMP_UNKNOWN', 'UNKNOWN']:
                        needs_retry = True
                        remove_links_ids.append(decrypted_link_id)
                    elif availability == 'OFFLINE':
                        is_offline = True
                        remove_links_ids.append(decrypted_link_id)

                if len(remove_links_ids) > 0:
                    # Remove all links that are not online from the JD2 link list
                    self.jd_device.linkgrabber.remove_links(remove_links_ids, [])

                if retry_counter < 2 and not is_online and needs_retry:
                    # Put back in queue
                    next_retry_job['retry'] = retry_counter + 1
                    self.new_jobs.append(next_retry_job)
                else:
                    # Finish job - Set Package status
                    # Online is the only state in that the package is still in JD2 link list
                    # In all other states the package is removed from the JD2 link list
                    if is_online:
                        next_retry_job['status'] = 'ONLINE'
                    elif needs_retry:
                        next_retry_job['status'] = 'UNKNOWN'
                    elif is_offline:
                        next_retry_job['status'] = 'OFFLINE'
                    elif is_already_done:
                        next_retry_job['status'] = 'ALREADY_DONE'
                    else:
                        next_retry_job['status'] = 'REAL_UNKNOWN'
                    self.filenames_jobs.append(next_retry_job)

                await asyncio.sleep(0)
            else:
                await asyncio.sleep(1)

    async def check_filenames_jobs(self):
        while not self.finished:
            if len(self.filenames_jobs) > 0:
                next_filenames_job = self.filenames_jobs.pop(0)

                decrypted_links = next_filenames_job.get('decrypted_links', [])

                for decrypted_link in decrypted_links:
                    availability = decrypted_link.get('availability', 'OFFLINE')
                    is_already_done = decrypted_link.get('is_already_done', False)
                    decrypted_link_id = decrypted_link.get('uuid', None)
                    name = decrypted_link.get('name', None)
                    if name is None or decrypted_link_id is None:
                        continue  # should not happen

                    if not is_already_done and availability == 'ONLINE':
                        new_name = name.replace('_', ' ')
                        if new_name != name:
                            # Rename all links that are online to match our convention
                            self.jd_device.linkgrabber.rename_link(decrypted_link_id, new_name)
                            await asyncio.sleep(0)

                self.checked_jobs.append(next_filenames_job)

                await asyncio.sleep(0)
            else:
                await asyncio.sleep(1)
