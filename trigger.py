import schedule
import time
import random
from datetime import datetime, timezone
import httpx

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

cred = credentials.Certificate('botcreator-9669d-firebase-adminsdk-3zoyl-2a9551a5f8.json')
firebase_admin.initialize_app(cred)
db = firestore.client()


def get_headers(user_id: str):
    data = {'end_user': user_id, 'provider': 'twitter', 'username': 'rushabha8@gmail.com', 'password': 'password'}
    r = httpx.post("https://2d89-14-143-179-162.in.ngrok.io/get-access-token", data=data)
    token = r.text.strip('"')
    headers = {'Authorization': f"Bearer {token}", 'Accept': 'application/json'}
    return headers


def do_retweet(user_id: str, tweet_id: str):
    headers = get_headers(user_id=user_id)
    # Todo: Verify response if retweet was successful.
    user_resp = httpx.get("https://api.twitter.com/2/users/me", headers=headers)
    user = user_resp.json()
    user_handle_id = user.get("data").get("id")
    resp = httpx.post(url=f"https://api.twitter.com/2/users/{user_handle_id}/retweets", headers=headers,
                      json={"tweet_id": tweet_id})
    print(resp.json())


def get_tweet_id(handle_id: str):
    user_tweets = db.collection("users").document(handle_id).get()
    user_tweets_dict = user_tweets.to_dict()
    tweets_collection: list = user_tweets_dict.get("tweet_collection")
    tweets_collection_size: int = user_tweets_dict.get("collection_size")
    tweet_id = tweets_collection[random.randint(0, tweets_collection_size - 1)]
    return tweet_id


def trigger_schedules():
    print("Triggering a schedule")
    snapshots = db.collection("schedules").where("next_trigger", '<=',
                                                 int(round(datetime.now(tz=timezone.utc).timestamp()))).get()
    for snap in snapshots:
        snap_dict = snap.to_dict()
        tweet_id: str = get_tweet_id(handle_id=snap_dict.get("handle_id"))
        do_retweet(user_id=snap_dict.get("user_id"), tweet_id=tweet_id)
        schedule_ref = db.collection("schedules").document(snap.id)
        schedule_ref.update({"next_trigger": snap_dict.get("interval") +
                            int(round(datetime.now(tz=timezone.utc).timestamp()))})


schedule.every(1).minutes.do(trigger_schedules)

while True:
    schedule.run_pending()
    time.sleep(60)
