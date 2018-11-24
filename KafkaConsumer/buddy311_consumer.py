import json
from kafka import KafkaConsumer
import mysql.connector as mariadb
import requests
import logging
import time

logging.basicConfig(filename='/var/log/buddy311consumer.log',
	filemode='a',
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%H:%M:%S',
	level=logging.INFO)

# Create the database connection
mariadb_connection = mariadb.connect(host='database', user='buddy311dba', password='AlexChrisPaulStan', database='buddy311')
cursor = mariadb_connection.cursor()

def KafkaConnect ():
	LoopDelay=1;
	Connected=False
	while Connected == False:
		try:
			if LoopDelay > 60:
				logging.info("Does this happen?")
				LoopDelay = 60
			else:
				LoopDelay += 1
				logging.info("increased loop delay to %d seconds" % LoopDelay)
			consumer = KafkaConsumer('buddy311', bootstrap_servers=['kafkaserver1:9092'], value_deserializer=lambda m: json.loads(m.decode('utf-8')))
			logging.info("Connected successfully to Kafka")
			Connected=True
		except:
			logging.info("Failed to connect to kafka, delaying %d seconds" % LoopDelay)
			time.sleep(LoopDelay)
	logging.info("Returning kafka connection")
	return consumer
#consumer = KafkaConsumer('buddy311', bootstrap_servers=['kafkaserver1:9092'], value_deserializer=lambda m: json.loads(m.decode('utf-8')))
consumer = KafkaConnect()

for message in consumer:
	logging.info("Message value: %s" % message.value)

	# send request to buddy311 REST server
	response=requests.post("http://buddy311Class:31102/buddy311/v0.1/", json=message.value)
	logging.info("Response is: %s" % response.json())

	# update the database
	service_code_probability = float(response.json()['service_code_proba'])
	service_code = response.json()['service_code']
	logging.info("Response service_code is: %s, probability %f" % (service_code, service_code_probability))
	try:
		cursor.execute("update requests set service_code=\"%s\", service_code_proba=%f where service_request_id = %d" % (service_code, service_code_probability, message.value['service_request_id']))
		mariadb_connection.commit()
	except:
		mariadb_connection = mariadb.connect(host='database', user='buddy311dba', password='AlexChrisPaulStan', database='buddy311')
		cursor = mariadb_connection.cursor()
		cursor.execute("update requests set service_code=\"%s\", service_code_proba=%f where service_request_id = %d" % (service_code, service_code_probability, message.value['service_request_id']))
		mariadb_connection.commit()

