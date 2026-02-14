from datetime import datetime, timedelta

import airflow
from airflow import DAG
from airflow.operators.python import PythonOperator


default_args = {
    'owner': 'airflow',
    'start_date': datetime(2020, 1, 1),
}

def get_data():
    # import libraries avoid scheduler repeatedly import
    import requests
    print("Getting data from API")

    try:
        response = requests.get('https://dummyjson.com/users')

        data = response.json()

        profile = data['users'][0]
        print("Profile data")
        print(profile)
        return profile
    except Exception as e:
        print(f"Getting data from API failed: {e}")


def format_data():


def kafka_stream(**kwargs):
    import json



# with DAG(dag_id='kafka_stream',
#          default_args=default_args,
#          schedule='@daily',
#          max_active_runs=1,
#          catchup=False) as dag:
#
#     streaming_task = PythonOperator(
#         task_id='streaming_task_from_api',
#         python_callable=kafka_stream,
#     )

get_data()