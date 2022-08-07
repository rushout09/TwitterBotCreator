from typing import Optional

import pyrebase
import json
import fastapi
import httpx

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from requests import HTTPError
from fastapi import Depends, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.param_functions import Form

app = fastapi.FastAPI()

cred = credentials.Certificate('botcreator-9669d-firebase-adminsdk-3zoyl-2a9551a5f8.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

httpxClient = httpx.AsyncClient()
pb = pyrebase.initialize_app(json.load(open('firebase_config.json')))
auth = pb.auth()


@app.post("/signup")
async def signup(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user = auth.create_user_with_email_and_password(
            email=form_data.username,
            password=form_data.password
        )
        # Todo: verify if email sent.
        email_verification = auth.send_email_verification(id_token=user.get("idToken"))
        return JSONResponse(
            content={'message': f'Successfully created user. Please verify your email {user.get("email")}'},
            status_code=200)
    except HTTPError as e:
        error_dict = json.loads(e.strerror)["error"]
        return HTTPException(detail={'message': error_dict.get("message")}, status_code=error_dict.get("code"))


def validate_login_creds(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user = auth.sign_in_with_email_and_password(form_data.username, form_data.password)
        account_info = auth.get_account_info(id_token=user.get("idToken"))
        user_email_verified = account_info.get("users")[0].get("emailVerified")
        if not user_email_verified:
            str_error = {
                "error": {
                    "message": "Email not verified. Please verify email.",
                    "code": 400
                }
            }
            error = HTTPError
            error.strerror = json.dumps(str_error)
            raise error
        user_id: str = account_info.get("users")[0].get("localId")
        return user_id
    except HTTPError as e:
        error_dict = json.loads(e.strerror)["error"]
        return HTTPException(detail={'message': error_dict.get("message")}, status_code=error_dict.get("code"))


@app.post("/authorize-twitter")
async def authorize_twitter(user_id: str = Depends(validate_login_creds)):
    data = {'end_user': user_id, 'username': 'rushabha8@gmail.com', 'password': 'password'}
    r = httpx.post("http://127.0.0.1/authorize-twitter", data=data)
    return r.text.strip("'")


@app.get("/home")
async def home():
    return "home"


async def get_tweets_from_handle(handle_id: str, user_id: str):
    next_token: Optional[str] = None
    first_call = True
    tweet_list: list = []
    headers = await get_headers(user_id=user_id)
    while next_token is not None or first_call:
        first_call = False
        if next_token is None:
            resp = httpx.get(url=f"https://api.twitter.com/2/users/{handle_id}/tweets?max_results=100&exclude=retweets"
                                 f"%2Creplies&start_time=2012-01-01T00%3A00%3A00Z&end_time=2022-07-01T00%3A00%3A00Z",
                             headers=headers)
        else:
            resp = httpx.get(url=f"https://api.twitter.com/2/users/{handle_id}/tweets?max_results=100&exclude=retweets"
                                 f"%2Creplies&start_time=2012-01-01T00%3A00%3A00Z&end_time=2022-07-01T00%3A00%3A00Z"
                                 f"&pagination_token={next_token}",
                             headers=headers)
        resp_dict: dict = resp.json()
        meta: dict = resp_dict.get("meta")
        result_count: int = meta.get("result_count")
        if result_count == 100:
            next_token = meta.get("next_token")
        else:
            next_token = None
        page_tweet_list: list = resp_dict.get("data")
        tweet_list.extend(page_tweet_list)
    return tweet_list


async def save_tweets_from_handle(handle_id: str, user_id: str):
    tweet_list: list = await get_tweets_from_handle(handle_id=handle_id, user_id=user_id)
    tweet_list_size = len(tweet_list)
    tweet_id_list = []
    for tweet in tweet_list:
        tweet_id_list.append(tweet.get("id"))

    db.collection("users").document(handle_id).\
        set({"collection_size": tweet_list_size, "tweet_collection": tweet_id_list})
    # tweets_coll_ref = db.collection("users").document(handle_id).collection("tweets")
    # start_interval = 0
    # if len(tweet_list) < 500:
    #     end_interval = len(tweet_list)
    # else:
    #     end_interval = 500
    # count = 0
    # while end_interval <= len(tweet_list):
    #     batch = db.batch()
    #     for tweet in tweet_list[start_interval:end_interval]:
    #         tweet_ref = tweets_coll_ref.document(count)
    #         count = count + 1
    #         batch.set(tweet_ref, tweet)
    #     batch.commit()
    #     start_interval = end_interval
    #     if end_interval == len(tweet_list):
    #         break
    #     if len(tweet_list) - end_interval < 500:
    #         end_interval = len(tweet_list)
    #     else:
    #         end_interval = 500


async def get_headers(user_id: str):
    data = {'end_user': user_id, 'provider': 'twitter', 'username': 'rushabha8@gmail.com', 'password': 'password'}
    r = httpx.post("http://127.0.0.1/get-access-token", data=data)
    token = r.text.strip('"')
    headers = {'Authorization': f"Bearer {token}", 'Accept': 'application/json'}
    return headers


async def save_schedule(handle_id: str, user_id: str, interval: int):
    schedule_ref = db.collection("schedules").document()
    schedule_ref.set({
        "user_id": user_id,
        "handle_id": handle_id,
        "interval": interval,
        "next_trigger": 0
    })


@app.post("/retweet-user-timeline")
async def retweet_user_timeline(user_handle: str = Form(), frequency: str = Form(),
                                user_id: str = Depends(validate_login_creds)):
    headers = await get_headers(user_id=user_id)
    resp = httpx.get(url=f"https://api.twitter.com/2/users/by/username/{user_handle}?user.fields=id", headers=headers)
    resp_dict: dict = resp.json()
    handle_id: str = ""
    if 168 < int(frequency) < 0:
        return HTTPException(detail="Frequency should be between 0 and 168.", status_code=status.HTTP_400_BAD_REQUEST)

    if 'data' in resp_dict.keys():
        handle_id = resp_dict.get("data").get("id")
        # Todo: check if Tweets exists for particular handle_id, do not call the below function.
        await save_tweets_from_handle(handle_id=handle_id, user_id=user_id)
        await save_schedule(handle_id=handle_id, user_id=user_id, interval=int(frequency) * 3600)
    else:
        error_detail = resp_dict.get("errors")[0].get("detail")
        return HTTPException(detail=error_detail, status_code=status.HTTP_400_BAD_REQUEST)
