import argparse
import base64
import json
import os
import shutil
import sys

import dateutil.parser
import requests

from .exceptions import *


def prepare_dir(path):
    if not path.endswith("/"):
        path = os.path.dirname(path)

    if not os.path.isdir(path):
        os.makedirs(path)


class Downloader:
    def __init__(self, api_key, api_secret):
        self.bearer_token = self.bearer(api_key, api_secret)
        print("Bearer token is " + self.bearer_token)
        self.last_tweet = None
        self.count = 0

    def download_images(
        self, user, save_dest, size="large", limit=3200, rts=False, include_video=False
    ):
        """Download and save images that user uploaded.

        Args:
            user: User ID.
            save_dest: The directory where images will be saved.
            size: Which size of images to download.
            rts: Whether to include retweets or not.
        """

        if not os.path.isdir(save_dest):
            try:
                prepare_dir(save_dest)
            except Exception as e:
                raise InvalidDownloadPathError(str(e))

        num_tweets_checked = 0
        tweets = self.get_tweets(user, self.last_tweet, limit, rts)
        if not tweets:
            print("Got an empty list of tweets")

        while len(tweets) > 0 and num_tweets_checked < limit:
            for tweet in tweets:
                # # create a file name using the timestamp of the image
                # timestamp = dateutil.parser.parse(tweet["created_at"]
                #                                  ).timestamp()
                # ts = str(int(timestamp))

                id_str = tweet["id_str"]

                # save the image
                images = self.extract_media_list(tweet, include_video)
                for i, image in enumerate(images, 1):
                    self.save_media(image, save_dest, f"{id_str}-{i}", size)
                    num_tweets_checked += 1
                self.last_tweet = tweet["id"]

            tweets = self.get_tweets(user, self.last_tweet, count=limit)

    def bearer(self, key, secret):
        """Receive the bearer token and return it.

        Args:
            key: API key.
            secret: API string.
        """

        # setup
        credential = base64.b64encode(
            bytes("{}:{}".format(key, secret), "utf-8")
        ).decode()
        url = "https://api.twitter.com/oauth2/token"
        headers = {
            "Authorization": "Basic {}".format(credential),
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }
        payload = {"grant_type": "client_credentials"}

        # post the request
        r = requests.post(url, headers=headers, params=payload)

        # check the response
        if r.status_code == 200:
            return r.json()["access_token"]
        else:
            raise BearerTokenNotFetchedError()

    def get_tweets(self, user, start=None, count=200, rts=False):
        """Download user's tweets and return them as a list.

        Args:
            user: User ID.
            start: Tweet ID.
            rts: Whether to include retweets or not.
        """

        # setup
        bearer_token = self.bearer_token
        url = "https://api.twitter.com/1.1/statuses/user_timeline.json"
        headers = {"Authorization": "Bearer {}".format(bearer_token)}
        payload = {"screen_name": user, "count": count, "include_rts": rts}
        if start:
            payload["max_id"] = start

        # get the request
        r = requests.get(url, headers=headers, params=payload)

        # check the response
        if r.status_code == 200:
            tweets = r.json()
            if len(tweets) == 1:
                return []
            else:
                print("Got " + str(len(tweets)) + " tweets")
                return tweets if not start else tweets[1:]
        else:
            print(
                "An error occurred with the request, status code was "
                + str(r.status_code)
            )
            return []

    def extract_media_list(self, tweet, include_video):
        """Return the url of the image embedded in tweet.

        Args:
            tweet: A dict object representing a tweet.
        """
        rv = []

        extended = tweet.get("extended_entities")
        if not extended:
            return rv

        if "media" in extended:
            for x in extended["media"]:
                if x["type"] == "photo":
                    url = x["media_url"]
                    rv.append(url)
                elif x["type"] in ["video", "animated_gif"]:
                    if include_video:
                        variants = x["video_info"]["variants"]
                        variants.sort(key=lambda x: x.get("bitrate", 0))
                        url = variants[-1]["url"].rsplit('?tag')[0]
                        rv.append(url)
                # else:
                #     import pdb
                #
                #     pdb.set_trace()
        return rv

    def save_media(self, image, path, name, size="large"):
        """Download and save an image to path.

        Args:
            image: The url of the image.
            path: The directory where the image will be saved.
            name: It is used for naming the image.
            size: Which size of images to download.
        """

        if image:
            # image's path with a new name
            ext = os.path.splitext(image)[1]
            save_dest = os.path.join(path, name + ext)
            if ext not in [".mp4"]:
                real_url = image + ":" + size
            else:
                real_url = image

            # save the image in the specified directory (or don't)
            prepare_dir(save_dest)
            if not (os.path.exists(save_dest)):
                print("Saving " + image)

                r = requests.get(real_url, stream=True)
                if r.status_code == 200:
                    with open(save_dest, "wb") as f:
                        r.raw.decode_content = True
                        shutil.copyfileobj(r.raw, f)
                    self.count += 1

            else:
                print(f"Skipping {image} because it was already dowloaded")