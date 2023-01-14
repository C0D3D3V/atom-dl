import asyncio
import traceback


from atom_dl.config_helper import Config
from atom_dl.my_jd_api import MyJdApi, MYJDException
from atom_dl.utils import Log, load_list_from_json, PathTools as PT, append_list_to_json


class JobsFeeder:
    def __init__(self):
        self.finished = False
        self.new_jobs = []
        self.max_parallel_decrypt_jobs = 15
        self.decrypt_jobs = []
        self.decrypted_jobs = []
        self.urls_jobs = []
        self.checked_jobs = []

        Log.info("Try to connect to MyJDownloader...")
        config = Config()
        try:
            my_jd_username = config.get_my_jd_username()
            my_jd_password = config.get_my_jd_password()
            my_jd_device = config.get_my_jd_device()
        except ValueError as config_error:
            Log.error(str(config_error))
            Log.error(
                "Please set all MyJDownloader settings in your configuration:\n"
                + "{my_jd_username, my_jd_password, my_jd_device}"
            )
            exit(-1)
        self.jd = MyJdApi()
        self.jd_device = None
        try:
            self.jd.set_app_key("Atom-Downloader")
            self.jd.connect(my_jd_username, my_jd_password)
            self.jd_device = self.jd.get_device(my_jd_device)
        except MYJDException as jd_error:
            Log.error(str(jd_error).strip())
            Log.error("Error no connection could be established with MyJDownloader.")
            exit(-2)

    def __del__(self):
        try:
            self.jd.disconnect()
        except MYJDException as jd_error:
            Log.error(str(jd_error).strip())

    def process(self):
        Log.debug('Start working on jobs...')
        json_file_path = PT.get_path_of_jobs_json()
        self.new_jobs = load_list_from_json(json_file_path)

        if len(self.new_jobs) > 0:
            asyncio.run(self.jd_job_chain())

    async def jd_job_chain(self):
        gather_jobs = asyncio.gather(
            *[
                self.send_jobs_to_jd(),
                self.check_decrypt_jobs(),
                self.check_decrypted_jobs(),
                self.check_urls_jobs(),
                self.check_finish_condition(),
            ]
        )
        try:
            await gather_jobs
        except Exception:
            traceback.print_exc()
            gather_jobs.cancel()
            exit(1)

        append_list_to_json(PT.get_path_of_checked_jobs_json(), self.checked_jobs)

    async def check_finish_condition(self):
        while True:
            if (
                len(self.new_jobs) == 0
                and len(self.decrypt_jobs) == 0
                and len(self.decrypted_jobs) == 0
                and len(self.urls_jobs) == 0
            ):
                self.finished = True
                return
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

    async def check_urls_jobs(self):
        while not self.finished:
            if len(self.urls_jobs) > 0:
                next_retry_job = self.urls_jobs.pop(0)

                decrypted_links = next_retry_job.get('decrypted_links', [])
                retry_counter = next_retry_job.get('retry', 0)

                is_online = False
                needs_retry = False
                remove_links_ids = []
                for decrypted_link in decrypted_links:
                    availability = decrypted_link.get('availability', 'OFFLINE')
                    decrypted_link_id = decrypted_link.get('uuid', None)
                    if decrypted_link_id is None:
                        continue  # should not happen
                    if availability == 'ONLINE':
                        is_online = True
                    elif availability in ['TEMP_UNKNOWN', 'UNKNOWN']:
                        needs_retry = True
                        remove_links_ids.append(decrypted_link_id)
                    elif availability == 'OFFLINE':
                        remove_links_ids.append(decrypted_link_id)

                if len(remove_links_ids) > 0:
                    _ = self.jd_device.linkgrabber.remove_links(remove_links_ids, [])
                    pass

                if retry_counter < 2 and is_online is False and needs_retry is True:
                    # Put back in queue
                    next_retry_job['retry'] = retry_counter + 1
                    self.new_jobs.append(next_retry_job)
                else:
                    # Finish job
                    if is_online:
                        next_retry_job['status'] = 'ONLINE'
                    elif needs_retry:
                        next_retry_job['status'] = 'UNKNOWN'
                    else:
                        next_retry_job['status'] = 'OFFLINE'
                    self.checked_jobs.append(next_retry_job)

                await asyncio.sleep(0)
            else:
                await asyncio.sleep(1)
