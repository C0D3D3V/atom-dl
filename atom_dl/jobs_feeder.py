import asyncio
import traceback


from atom_dl.config_helper import Config
from atom_dl.my_jd_api import MyJdApi, MYJDException
from atom_dl.utils import Log, load_list_from_json, PathTools as PT


class JobsFeeder:
    def __init__(self):
        self.finished = False
        self.all_jobs = []
        self.max_parallel_decrypt_jobs = 15
        self.decrypt_jobs = []
        self.decrypted_jobs = []

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
        self.all_jobs = load_list_from_json(json_file_path)

        if len(self.all_jobs) > 0:
            asyncio.run(self.jd_job_chain())

    async def jd_job_chain(self):
        gather_jobs = asyncio.gather(
            *[
                self.send_jobs_to_jd(),
                self.check_decrypt_jobs(),
                self.check_decrypted_jobs(),
                self.check_finish_condition(),
            ]
        )
        try:
            await gather_jobs
        except Exception:
            traceback.print_exc()
            gather_jobs.cancel()
            exit(1)

    async def check_finish_condition(self):
        while True:
            if len(self.all_jobs) == 0 and len(self.decrypt_jobs) == 0 and len(self.decrypted_jobs) == 0:
                self.finished = True
                return
            await asyncio.sleep(1)

    async def send_jobs_to_jd(self):
        while not self.finished:
            if len(self.all_jobs) > 0 and len(self.decrypt_jobs) < self.max_parallel_decrypt_jobs:
                next_job = self.all_jobs.pop()
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

                for job_status in result:
                    job_status_crawling = job_status.get('crawling', False)
                    job_status_id = job_status.get('jobId', None)
                    if job_status_id is None:
                        continue  # should not happen
                    if not job_status_crawling:
                        job_idx = None
                        for idx, decrypt_job in enumerate(self.decrypt_jobs):
                            job_id = decrypt_job.get('crawl_job_id', None)
                            if job_id is None:
                                continue  # should not happen
                            if job_id == job_status_id:
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
                next_decrypted_job = self.decrypted_jobs.pop()

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
                is_online = False
                needs_retry = False
                decrypted_links = self.jd_device.linkgrabber.query_links(link_querry)

                remove_jobs = []
                for decrypted_link in decrypted_links:
                    availability = decrypted_link.get('availability', 'OFFLINE')
                    if availability == 'ONLINE':
                        is_online = True
                    elif availability in ['TEMP_UNKNOWN', 'UNKNOWN']:
                        needs_retry = True
                        pass  # retry
                    elif availability == 'OFFLINE':
                        is_online = False
                        pass  # remove

                next_decrypted_job['decrypted_links'] = decrypted_links 
                if not is_online and not needs_retry:
                    # finished task, status = offline
                elif is_online:
                    # finished task, status = online
                elif needs_retry:
                    if retries < 2:
                        #retry entscheide in remove function -> entferne erst und wenn es unkow war dann retry wenn versuch noch verfügbar ansonsten finish mit status unkow
                    else:
                        # finished task, status = unknow



                await asyncio.sleep(0)
            else:
                await asyncio.sleep(1)
