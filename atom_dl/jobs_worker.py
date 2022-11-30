from typing import Dict, List

from atom_dl.utils.logger import Log


class JobsWorker:
    def handle_jobs(self, jobs: List[Dict]):
        Log.debug('Start working on jobs...')

        Log.success('All jobs done')
