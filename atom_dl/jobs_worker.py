from typing import Dict, List

from atom_dl.utils import Log


class JobsWorker:
    def handle_jobs(self, jobs: List[Dict]):
        Log.debug('Start working on jobs...')

        for job in jobs:
            print(job)

        Log.success('All jobs done')
