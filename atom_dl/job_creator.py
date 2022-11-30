from typing import Dict

from atom_dl.feed_extractor.common import FeedInfoExtractor


class JobCreator:
    def __init__(
        self,
        job_description: Dict,
    ):
        self.in_title = job_description.get('in_title', None)
        self.in_feeds = job_description.get('in_feeds', None)

    def create_job(self, post: Dict, extractor: FeedInfoExtractor) -> Dict:
        """
        Creates an job dictionary based on a given post
        """

        return post

    def process(self, post: Dict, extractor: FeedInfoExtractor) -> Dict:
        """
        If the post matches the job description, an job item is returned, else None is returned.
        """

        matches_job_definition = True
        if self.in_title is not None and self.in_title != '':
            # Check if title matches job definition
            if post.get('title', '').find(self.in_title) < 0:
                matches_job_definition = False

        if matches_job_definition:
            return self.create_job(post, extractor)
        else:
            return None

    def can_handle_feed(self, feed_name: str):
        if self.in_feeds is None:
            return True
        if isinstance(self.in_feeds, list) and feed_name in self.in_feeds:
            return True
        return False
