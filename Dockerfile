FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

COPY ./firebase_config.json /code/firebase_config.json

COPY ./botcreator-9669d-firebase-adminsdk-3zoyl-2a9551a5f8.json /code/botcreator-9669d-firebase-adminsdk-3zoyl-2a9551a5f8.json

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./main.py /code/main.py

COPY ./trigger.py /code/trigger.py

CMD ["python", "trigger.py", "&&", "gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "127.0.0.1:8100"]
