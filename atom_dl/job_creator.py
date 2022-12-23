from typing import Dict, List

from atom_dl.feed_extractor.common import FeedInfoExtractor


class JobCreator:
    def __init__(
        self,
        job_description: Dict,
    ):
        self.in_title = job_description.get('in_title', None)
        self.in_feeds = self.as_list_or_none(job_description.get('in_feeds', None))
        self.in_categories = self.as_list_or_none(job_description.get('in_categories', None))

    def as_list_or_none(self, obj) -> List:
        if obj is not None and not isinstance(obj, list):
            return [obj]
        return obj

    def create_job(self, post: Dict, extractor: FeedInfoExtractor) -> Dict:
        """
        Creates an job dictionary based on a given post
        """

        destination_path = extractor.get_destination_path(post)
        package_name = extractor.get_package_name(post)
        extractor_key = extractor.fie_key()

        job_dict = {
            "title": post.get("title", 'Untitled'),
            "page_link": post.get("page_link", 'No page_link'),
            "page_id": post.get("page_link", 'No page_id'),
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

        matches_job_definition = True
        if self.in_title is not None:
            # Check if title matches job definition
            matches_job_definition = False
            if post.get('title', '').find(self.in_title) >= 0:
                matches_job_definition = True

        if self.in_categories is not None:
            # Check if any category matches any category in job definition
            matches_job_definition = False
            for category in self.in_categories:
                if category in post.get('categories', []):
                    matches_job_definition = True
                    break

        if matches_job_definition:
            return self.create_job(post, extractor)
        else:
            return None

    def can_handle_feed(self, feed_name: str):
        if self.in_feeds is None or feed_name in self.in_feeds:
            return True
        return False
