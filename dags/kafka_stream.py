from datetime import datetime
import uuid
from airflow.decorators import dag, task

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2026, 2, 1),
}

def get_data():
    # import libraries avoid scheduler repeatedly import
    import requests
    import random
    print("Getting data from API")

    try:
        response = requests.get('https://dummyjson.com/users')

        print("Got data from API...")
        data = response.json()

        profile = random.choice(data['users'])

        return profile
    except Exception as e:
        print(f"Getting data from API failed: {e}")


def format_data(response):
    data = {}

    # if not cast into string, json cannot parse UUID object
    data['id'] = str(uuid.uuid4())
    data['first_name'] = response['firstName']
    data['last_name'] = response['lastName']
    data['gender'] = response['gender']
    data['address'] = str(response['address']['address'] + "," + response['address']['city'] \
                          + ","  + response['address']['state'] + " " + response['address']['stateCode'] \
                          + "," + response['address']['country'])

    data['email'] = response['email']
    data['username'] = response['username']
    data['birth_date'] = response['birthDate']
    data['phone'] = response['phone']
    data['image'] = response['image']

    return data

@dag(
    dag_id='kafka_stream',
    default_args=default_args,
    schedule='@daily',
    max_active_runs=1,
    catchup=False
)
def kafka_stream_dag():

    # 定義 Task (使用 @task 裝飾器取代 PythonOperator)
    @task(task_id='streaming_task_from_api')
    def stream_data():
        import json
        import time
        import logging
        from kafka import KafkaProducer

        # if run on docker: should change to broker:29092, if not localhost:9092
        producer = KafkaProducer(bootstrap_servers=['broker:29092'], max_block_ms=5000)

        current_time  = time.time()

        while True:
            if time.time() > current_time + 60:
                break
            try:
                response = get_data()
                data = format_data(response)
                producer.send(topic='users_created', value=json.dumps(data).encode('utf-8'))
            except Exception as e:
                logging.error(f"An error occured: {e}")
                continue

    stream_data()


kafka_stream_dag()