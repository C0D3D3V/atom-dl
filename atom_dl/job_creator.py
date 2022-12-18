from typing import Dict, List

from atom_dl.feed_extractor.common import FeedInfoExtractor


class JobCreator:
    def __init__(
        self,
        job_description: Dict,
    ):
        # Todo: Create a rule set that allows complex job descriptions with an simple parsable syntax
        # Todo: Create an output template filename?
        # Todo: Create an replacement template for output filenames
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
        job_dict = {
            "title": post["title"],
            "page_link": post["page_link"],
            "page_id": post["page_id"],
            "download_links": post["download_links"],
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
