import json
from kafka import KafkaConsumer
import mysql.connector as mariadb
import requests
import logging

logging.basicConfig(filename='/var/log/buddy311consumer.log',
	filemode='a',
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%H:%M:%S',
	level=logging.INFO)

# Create the database connection
mariadb_connection = mariadb.connect(host='database', user='buddy311dba', password='AlexChrisPaulStan', database='buddy311')
cursor = mariadb_connection.cursor()

consumer = KafkaConsumer('buddy311', bootstrap_servers=['kafkaserver1:9092'], value_deserializer=lambda m: json.loads(m.decode('utf-8')))

for message in consumer:
    # message value and key are raw bytes -- decode if necessary!
	# e.g., for unicode: `message.value.decode('utf-8')`
	logging.info("Message value: ", message.value)

	# send request to buddy311 REST server
	response=requests.post("http://buddy311Class:31102/buddy311/v0.1/", json=message.value)
	logging.info("Response is: %s"% response.json())
	# update the database
	service_code_probability = float(response.json()['service_code_proba'])
	service_code = response.json()['service_code']
	logging.info("Response service_code is: %s, probability %f" % (service_code, service_code_probability))
	cursor.execute("update requests set service_code=\"%s\", service_code_proba=%f where service_request_id = %d" % (service_code, service_code_probability, message.value['service_request_id']))
	mariadb_connection.commit()

