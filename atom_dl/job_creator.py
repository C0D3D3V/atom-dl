import logging
from datetime import datetime, timedelta
from typing import Dict, List

from atom_dl.feed_extractor.common import FeedInfoExtractor
from atom_dl.utils import PathTools as PT


class JobCreator:
    def __init__(
        self,
        job_description: Dict,
        storage_path: str,
    ):
        self.storage_path = storage_path
        if len(job_description) == 0:
            logging.warning('Empty job description found! All Posts are jobs!')
        self.in_title = job_description.get('in_title', None)
        self.in_title_on_of = job_description.get('in_title_on_of', None)
        self.in_feeds = self.as_list_or_none(job_description.get('in_feeds', None))
        self.in_categories = self.as_list_or_none(job_description.get('in_categories', None))
        self.not_in_categories = self.as_list_or_none(job_description.get('not_in_categories', None))
        self.time_delta_updated = self.parse_time_delta(job_description.get('time_delta_updated', None))

    def parse_time_delta(self, delta: Dict):
        if delta is None:
            return None
        allowed_keys = ['days', 'seconds', 'microseconds', 'milliseconds', 'minutes', 'hours', 'weeks']
        if not isinstance(delta, dict):
            raise ValueError(
                f'Time delta needs to be a dictionary with at least one of the following keys: {allowed_keys}'
            )
        for key in delta:
            if key not in allowed_keys:
                raise ValueError(f'Time delta is only allowed to have the following keys: {allowed_keys}')
        return timedelta(**delta)

    def as_list_or_none(self, obj) -> List:
        if obj is not None and not isinstance(obj, list):
            return [obj]
        return obj

    def create_job(self, post: Dict, extractor: FeedInfoExtractor) -> Dict:
        """
        Creates an job dictionary based on a given post
        """

        top_category = extractor.get_top_category(post).value
        package_name = PT.to_valid_name(extractor.get_package_name(post))
        destination_path = PT.make_path(self.storage_path, top_category, package_name)
        extractor_key = extractor.fie_key()

        job_dict = {
            "title": post.get("title", 'Untitled'),
            "page_link": post.get("page_link", 'No page_link'),
            "page_id": post.get("page_id", 'No page_id'),
            "download_links": post.get("download_links", []),
            "destination_path": destination_path,
            "package_name": package_name,
            "password": post.get("password", None),
            "extractor_key": extractor_key,
        }

        return job_dict

    def process(self, post: Dict, extractor: FeedInfoExtractor) -> Dict:
        """
        If the post matches the job description, an job item is returned, else None is returned.
        """

        if self.time_delta_updated is not None:
            # Check if post is too old for time delta
            updated_date = datetime.strptime(post.get('updated_date', ''), '%Y-%m-%dT%H:%M:%SZ')
            if updated_date < datetime.utcnow() - self.time_delta_updated:
                return None

        if self.in_title is not None:
            # Check if title matches job definition
            if post.get('title', '').find(self.in_title) < 0:
                return None

        if self.in_title_on_of is not None:
            # Check if title matches any title in job definition
            matches_job_definition = False
            for in_title in self.in_title_on_of:
                if post.get('title', '').find(in_title) >= 0:
                    matches_job_definition = True
                    break
            if not matches_job_definition:
                return None

        if self.in_categories is not None:
            # Check if any category matches any category in job definition
            matches_job_definition = False
            post_categories = post.get('categories', [])
            for category in self.in_categories:
                if category in post_categories:
                    matches_job_definition = True
                    break
            if not matches_job_definition:
                return None

        if self.not_in_categories is not None:
            # Check if any category matches any category in job definition
            matches_job_definition = True
            post_categories = post.get('categories', [])
            for category in self.not_in_categories:
                if category in post_categories:
                    matches_job_definition = False
                    break
            if not matches_job_definition:
                return None

        return self.create_job(post, extractor)

    def can_handle_feed(self, feed_name: str):
        if self.in_feeds is None or feed_name in self.in_feeds:
            return True
        return False
