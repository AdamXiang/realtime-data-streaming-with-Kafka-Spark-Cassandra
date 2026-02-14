import logging

from cassandra.cluster import Cluster
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType


def create_keyspace(session):

    # keyspace is just like schema in RDBMS
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS spark_streams
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};
    """)

    print("Keyspace created successfully!")


def create_table(session):
    session.execute("""
    CREATE TABLE IF NOT EXISTS spark_streams.created_users (
        id UUID PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        gender TEXT,
        address TEXT,
        email TEXT,
        username TEXT,
        birth_date TEXT,
        phone TEXT,
        image TEXT);
    """)

    print("Table created successfully!")


def insert_data(session, **kwargs):
    print("Inserting data...")

    user_id = kwargs.get('id')
    first_name = kwargs.get('first_name')
    last_name = kwargs.get('last_name')
    gender = kwargs.get('gender')
    address = kwargs.get('address')
    email = kwargs.get('email')
    username = kwargs.get('username')
    birth_date = kwargs.get('birth_date')
    phone = kwargs.get('phone')
    image = kwargs.get('image')

    try:
        session.execute("""
            INSERT INTO spark_streams.created_users(id, first_name, last_name, gender, address, 
                email, username, birth_date, phone, image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, first_name, last_name, gender, address,
              email, username, birth_date, phone, image))
        logging.info(f"Data inserted for {first_name} {last_name}")

    except Exception as e:
        logging.error(f'Could not insert data due to {e}')


def create_spark_connection():
    spark_conn = None

    try:
        # in Dokcer, use -> cassandra
        spark_conn = SparkSession.builder \
            .appName('SparkDataStreaming') \
            .config('spark.jars.packages', "com.datastax.spark:spark-cassandra-connector_2.13:3.4.1,"
                                           "org.apache.spark:spark-sql-kafka-0-10_2.13:3.4.1") \
            .config('spark.cassandra.connection.host', 'localhost') \
            .getOrCreate()

        spark_conn.sparkContext.setLogLevel("ERROR")
        logging.info("Spark connection created successfully!")

    except Exception as e:
        logging.error(f"Couldn't create the spark session due to exception {e}")

    return spark_conn


def connect_to_kafka(spark_conn):
    """
    Establishes a streaming connection to Kafka using the provided SparkSession.

    This function connects to the local Kafka broker ('localhost:9092'), subscribes
    to the 'users_created' topic, and starts reading the data stream from the
    earliest available offset.

    :param spark_conn: The active Spark session object used to read the stream.
    :type spark_conn: pyspark.sql.SparkSession
    :return: A Structured Streaming DataFrame containing raw Kafka data, or None if the connection fails.
    :rtype: pyspark.sql.DataFrame or None
    """

    spark_df = None
    try:
        spark_df = spark_conn.readStream \
            .format('kafka') \
            .option('kafka.bootstrap.servers', 'localhost:9092') \
            .option('subscribe', 'users_created') \
            .option('startingOffsets', 'earliest') \
            .load()
        logging.info("kafka dataframe created successfully")

    except Exception as e:
        logging.warning(f"kafka dataframe could not be created because: {e}")

    return spark_df


def create_cassandra_connection():
    """
    Establishes a connection to the local Cassandra cluster.

    This function attempts to connect to a Cassandra database hosted on
    'localhost' and returns a session object for executing CQL queries.
    If the connection fails, it logs an error and returns None.

    Returns:
        cassandra.cluster.Session or None: A connected Cassandra session
            object if successful, otherwise None.
    """
    try:
        # connecting to the cassandra cluster
        cluster = Cluster(['localhost'])

        cas_session = cluster.connect()

        return cas_session

    except Exception as e:
        logging.error(f"Could not create cassandra connection due to {e}")
        return None


def create_selection_df_from_kafka(spark_df):
    schema = StructType([
        StructField("id", StringType(), False),
        StructField("first_name", StringType(), False),
        StructField("last_name", StringType(), False),
        StructField("gender", StringType(), False),
        StructField("address", StringType(), False),
        StructField("email", StringType(), False),
        StructField("username", StringType(), False),
        StructField("birth_date", StringType(), False),
        StructField("phone", StringType(), False),
        StructField("image", StringType(), False)
    ])

    sel = spark_df.selectExpr("CAST(value AS STRING)") \
        .select(from_json(col('value'), schema).alias('data')).select("data.*")
    print(sel)

    return sel


if __name__ == "__main__":
    # create spark connection
    spark_conn = create_spark_connection()

    if spark_conn is not None:
        # connect to kafka with spark connection
        spark_df = connect_to_kafka(spark_conn)
        selection_df = create_selection_df_from_kafka(spark_df)
        session = create_cassandra_connection()

        if session is not None:
            create_keyspace(session)
            create_table(session)

            logging.info("Streaming is being started...")

            # we want to do it with stream, not just batch insertion 
            streaming_query = (selection_df.writeStream.format("org.apache.spark.sql.cassandra")
                               .option('checkpointLocation', '/tmp/checkpoint') # in case there is any failure 
                               .option('keyspace', 'spark_streams')
                               .option('table', 'created_users')
                               .start())

            streaming_query.awaitTermination()