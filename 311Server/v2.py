"""
	GeoReport v2 Server
	-------------------

	Open311 GeoReport v2 Server implementation written in Flask.

	:copyright: (c) Miami-Dade County 2011
	:author: Julian Bonilla (@julianbonilla)
	:license: Apache License v2.0, see LICENSE for more details.
"""
from data import service_types, service_definitions, service_discovery, srs
from flask import Flask, render_template, request, abort, json, jsonify, make_response
import ssl
import mysql.connector as mariadb
import random
import requests, sys
import re
import datetime
from flask_cors import CORS
from kafka import SimpleProducer, KafkaClient

import logging

logging.basicConfig(filename='/var/log/buddy311admin.log',
	filemode='a',
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%H:%M:%S',
	level=logging.DEBUG)

# Configuration
DEBUG = True
ORGANIZATION = 'Buddy311'
JURISDICTION = 'Buddy311.org'

# Create the database connection
mariadb_connection=""
cursor=""

app = Flask(__name__)
cors = CORS(app, resources={r"*":{"origins": "*"}})
app.config.from_object(__name__)
app.config.from_envvar('GEOREPORT_SETTINGS', silent=True)

kafka = KafkaClient("kafkaserver1:9092")
producer=SimpleProducer(kafka)

def connectDatabase(phost, puser, ppassword, pdatabase):
	global mariadb_connection,cursor
	mariadb_connection = mariadb.connect(host=phost, user=puser, password=ppassword, database=pdatabase)
	cursor = mariadb_connection.cursor()


@app.route("/")
@app.route("/home")
def home():
	try:
		logging.debug('Starting home!')
		return render_template('index.html')
	except:
		logging.exception('Got exception on main handler')
		raise
	
@app.route("/admin")
def admin():
	api_url_base = 'https://buddy311.org/requests/get'
	response = requests.get(api_url_base).text

	# Seriously ensure it's json
	response = json.loads(json.loads(response))
	completed_count = len(response)
	current_utc_time = datetime.datetime.utcnow().strftime("%I:%M %p UTC - %B %d, %Y")
	return render_template('admin.html', completed_json_data = response, completed_count = completed_count, 
			      current_utc_time = current_utc_time)

@app.route("/references")
def references():
	return render_template('references.html')

@app.route("/siri")
def siri():
	return render_template('siri_shortcut.html')

# added for testing Paul
@app.route("/about")
def about():
	return render_template('about.html')

@app.route("/tech")
def tech():
	return render_template('tech.html')

@app.route('/version')
def index():
	return render_template('index.html', org=app.config['ORGANIZATION'], 
						   jurisdiction=app.config['JURISDICTION'])
# Test only
@app.route("/about2")
def about2():
	return render_template('about2.html')

@app.route('/discovery.<format>')
def discovery(format):
	"""Service discovery mechanism required for Open311 APIs."""
	if format == 'json':
		return jsonify(service_discovery)
	elif format == 'xml':
		response = make_response(render_template('discovery.xml', discovery=service_discovery))
		response.headers['Content-Type'] = 'text/xml; charset=utf-8'
		return response
	else:
		abort(404)


@app.route('/services.<format>')
def service_list(format):
	"""Provide a list of acceptable 311 service request types and their 
	associated service codes. These request types can be unique to the
	city/jurisdiction.
	"""
	if format == 'json':
		response = make_response(json.dumps(service_types))
		response.headers['Content-Type'] = 'application/json; charset=utf-8'
		return response
	elif format == 'xml':
		response = make_response(render_template('services.xml', services=service_types))
		response.headers['Content-Type'] = 'text/xml; charset=utf-8'
		return response
	else:
		abort(404)


@app.route('/services/<service_code>.<format>')
def service_definition(service_code, format):
	"""Define attributes associated with a service code.
	These attributes can be unique to the city/jurisdiction.
	"""
	if service_code not in service_definitions:
		abort(404)

	if format == 'json':
		return jsonify(service_definitions[service_code])
	elif format == 'xml':
		response = make_response(render_template('definition.xml',
												 definition=service_definitions[service_code]))
		response.headers['Content-Type'] = 'text/xml; charset=utf-8'
		return response
	else:
		abort(404)


@app.route('/requests.<format>', methods=['GET', 'POST'])
def service_requests(format):
	"""Create service requests.
	Query the current status of multiple requests.
	"""
	if format not in ('json', 'xml'):
		abort(404)

	if request.method == 'POST':
		# Create service request
		sr = save(request)
		if format == 'json':
			return jsonify({"service_request_id": sr})
		elif format == 'xml':
			repsonse = make_response(render_template('success.xml', sr=sr))
			response.headers['Content-Type'] = 'text/xml; charset=utf-8'
			return response
	else:
		# Return a list of SRs that match the query
		sr = search(request.form)
		if format == 'json':
			response = make_response(json.dumps(srs))
			response.headers['Content-Type'] = 'application/json; charset=utf-8'
			return response
		elif format == 'xml':
			response = make_response(render_template('service-requests.xml', service_requests=srs))
			response.headers['Content-Type'] = 'text/xml; charset=utf-8'
			return response


@app.route('/requests/<service_request_id>.<format>')
def service_request(service_request_id, format):
	"""Query the current status of an individual request."""
	result = search(int(service_request_id))
	if format == 'json':

		return jsonify(result)
	elif format == 'xml':
		response = make_response(render_template('service-requests.xml', service_requests=[srs[0]]))
		response.headers['Content-Type'] = 'text/xml; charset=utf-8'
		return response
	else:
		abort(404)

@app.route('/requests/get', methods=['GET'])
def get_requests():
	logging.info("Received get to retrieve requests")
	try:
		cursor.execute("SELECT * from requests ORDER BY service_request_id DESC LIMIT 500")
	except:
		connectDatabase(phost='database', puser='buddy311dba', ppassword='AlexChrisPaulStan', pdatabase='buddy311')
		cursor.execute("SELECT * from requests ORDER BY service_request_id DESC LIMIT 500")
	
	row_headers=[x[0] for x in cursor.description]
	rv = cursor.fetchall()
	requestList = []
	for row in rv:
		requestList.append(dict(zip(row_headers, row)))
		
	# DEBUG #######################################
	print()
	print('requestList: ')
	print(requestList)
	print()
	print('len(completed):')
	print(len(requestList))
	print()
	###############################################
	
	jsonStr = json.dumps(requestList)
	
# 	query = {'count': len(requestList),
# 		 'jsonStr': jsonify(jsonStr)
# 		}
	
	return jsonify(jsonStr)

"""
handle calls from google assistant
"""

@app.route('/v1/assistant', methods=['POST','GET','OPTIONS'])
def processGoogleActionRequest():
	logging.info("Received POST request from google assistant")

	# Check if data provided
	if request.json == None:
		logging.info("No json message provided")
		return jsonify({'fulfillmentText': 'We did not receive a complaint, could you repeat that?'})
	some_json = request.json
	if some_json.get('queryResult') == None:
		logging.info("Empty message text")
		return jsonify({'fulfillmentText': 'We did not receive a complaint, could you repeat that?'})
	queryResult = some_json.get('queryResult')
	if queryResult.get('queryText') == None:
		logging.info("Empty message text")
		return jsonify({'fulfillmentText': 'We did not receive a complaint, could you repeat that?'})
	complaint = queryResult.get('queryText')
	logging.info("received: ", complaint)

	# Add the description and unknown field into the message
	request.json['description'] = complaint
	request.json['service_code'] = 'Unknown'
	sr = save(request)
	return jsonify({'fulfillmentText': "Thank you, your complaint number " + str(sr) + " has been recorded and is being processed. Do you want to make another complaint?"})

@app.route('/tokens/<token>.<format>')
def token(token, format):
	"""Get a service request id from a temporary token. This is unnecessary
	if the response from creating a service request does not contain a token.
	"""
	abort(404)

def sendToKafka(request_data):
	# send to kafka queue
	logging.info("Sending message to Kafka")
	producer.send_messages("buddy311", json.dumps(request_data).encode('utf-8'))

def search(service_request):
	"""Query service requests"""
	return_request = {}
	cursor.execute("""SELECT jurisdiction_id, service_code, latitude, longitude, address_string,
					address_id, email, device_id, account_id, first_name, last_name, phone,
					description, media_url FROM requests WHERE ticket_number=%d""" % (service_request))
	for jurisdiction_id, service_code, latitude, longitude, address_string, address_id, email, device_id, account_id, first_name, last_name, phone, description, media_url in cursor:
		return_request['jurisdiction_id'] = jurisdiction_id
		return_request['service_code'] = service_code
		return_request['latitude'] = latitude
		return_request['longitude'] = longitude
		return_request['address_string'] = address_string
		return_request['address_id'] = address_id
		return_request['email'] = email
		return_request['device_id'] = device_id
		return_request['account_id'] = account_id
		return_request['first_name'] = first_name
		return_request['last_name'] = last_name
		return_request['phone'] = phone
		return_request['description'] = description
		return_request['media_url'] = media_url
	return return_request

def save(service_request):
	"""Save service request"""

	insert_fields_string=""
	insert_values_string=""
	service_request_id=""
	request_data = service_request.get_json()
	if request_data.get('jurisdiction_id') != None:
		insert_fields_string += "jurisdiction_id,"
		insert_values_string += "\"" + request_data.get('jurisdiction_id')[:20] + "\","
	if request_data.get('service_code') != None:
		insert_fields_string += "service_code,"
		insert_values_string += "\"" + request_data.get('service_code')[:50] + "\","
	if request_data.get('latitude') != None:
		insert_fields_string += "latitude,"
		insert_values_string += "\"" + request_data.get('latitude') + "\","
	if request_data.get('longitude') != None:
		insert_fields_string += "longitude,"
		insert_values_string += "\"" + request_data.get('longitude') + "\","
	if request_data.get('address_string') != None:
		insert_fields_string += "address_string,"
		insert_values_string += "\"" + request_data.get('address_string')[:100] + "\","
	if request_data.get('email') != None:
		insert_fields_string += "email,"
		insert_values_string += "\"" + request_data.get('email')[:100] + "\","
	if request_data.get('device_id') != None:
		insert_fields_string += "device_id,"
		insert_values_string += "\"" + re.sub(r'\W+', '', request_data.get('device_id')[:100]) + "\","
	if request_data.get('account_id') != None:
		insert_fields_string += "account_id,"
		insert_values_string += "\"" + request_data.get('account_id')[:100] + "\","
	if request_data.get('first_name') != None:
		insert_fields_string += "first_name,"
		insert_values_string += "\"" + request_data.get('first_name')[:100] + "\","
	if request_data.get('last_name') != None:
		insert_fields_string += "last_name,"
		insert_values_string += "\"" + request_data.get('last_name')[:100] + "\","
	if request_data.get('phone') != None:
		insert_fields_string += "phone,"
		insert_values_string += "\"" + request_data.get('phone')[:100] + "\","
	if request_data.get('description') != None:
		insert_fields_string += "description,"
		insert_values_string += "\"" + request_data.get('description')[:1000] + "\","
	if request_data.get('media_url') != None:
		insert_fields_string += "media_url,"
		insert_values_string += "\"" + request_data.get('media_url')[:1000] + "\","

	logging.debug(insert_fields_string)
	logging.debug(insert_values_string)
	try:
		logging.warn("INSERT INTO requests (%s) VALUES (%s)" % (insert_fields_string[:-1], insert_values_string[:-1]))
		cursor.execute("INSERT INTO requests (%s) VALUES (%s)" % (insert_fields_string[:-1], insert_values_string[:-1]))
		mariadb_connection.commit()
		service_request_id=cursor.lastrowid
		logging.warn("Last request id is %d" % (service_request_id))
	except:
		# assuming a dropped connection so reconnect and try again
		logging.debug("Database connection exception, retrying")
		connectDatabase(phost='database', puser='buddy311dba', ppassword='AlexChrisPaulStan', pdatabase='buddy311')
		cursor.execute("INSERT INTO requests (%s) VALUES (%s)" % (insert_fields_string[:-1], insert_values_string[:-1]))
		mariadb_connection.commit()
		service_request_id=cursor.lastrowid

	logging.warn("again last request id is %d" % (service_request_id))
	# If our service code is unknown then send it on to Kafka
	if request_data.get('service_code').upper() == "UNKNOWN" or request_data.get('service_code') == None:
		logging.warn("Service code has value ", request_data.get('service_code'))
		request_data['service_request_id'] = service_request_id
		sendToKafka(request_data)
	else:
		logging.warn("Service code has value ", request_data.get('service_code'))
	logging.debug("Service request id is %d" % (service_request_id))
	return service_request_id


def pending_query():
	"""Query service requests where `service_code` == 'UNKNOWN'"""
	return_request = {}
	cursor.execute("""SELECT service_request_id, jurisdiction_id, service_code, latitude, longitude, address_string,
					address_id, email, device_id, account_id, first_name, last_name, phone,
					description, media_url FROM requests WHERE service_code='UNKNOWN'""")
# 	logging.info(f'{cursor}')
	for record in cursor:
# 		logging.info(f'{record}')
		return_request[record[service_request_id]] = {}
		for jurisdiction_id, service_code, latitude, longitude, address_string, address_id, email, device_id, account_id, first_name, last_name, phone, description, media_url in cursor:
			return_request[service_request_id]['jurisdiction_id'] = jurisdiction_id
			return_request[service_request_id]['service_code'] = service_code
			return_request[service_request_id]['latitude'] = latitude
			return_request[service_request_id]['longitude'] = longitude
			return_request[service_request_id]['address_string'] = address_string
			return_request[service_request_id]['address_id'] = address_id
			return_request[service_request_id]['email'] = email
			return_request[service_request_id]['device_id'] = device_id
			return_request[service_request_id]['account_id'] = account_id
			return_request[service_request_id]['first_name'] = first_name
			return_request[service_request_id]['last_name'] = last_name
			return_request[service_request_id]['phone'] = phone
			return_request[service_request_id]['description'] = description
			return_request[service_request_id]['media_url'] = media_url
	return return_request

def log_uncaught_exceptions(ex_cls, ex, tb):
	"""Set custom sys.excepthook behavior to output tracebacks to the log"""
	logging.critical(''.join(traceback.format_tb(tb)))
	logging.critical('{0}: {1}'.format(ex_cls, ex))

sys.excepthook = log_uncaught_exceptions

context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
context.load_verify_locations('/etc/ssl/certs/www_buddy311_org.ca-bundle')
context = ('/etc/pki/tls/certs/www_buddy311_org.crt', '/etc/ssl/private/www.buddy311.org.key')

connectDatabase(phost='database', puser='buddy311dba', ppassword='AlexChrisPaulStan', pdatabase='buddy311')

if __name__ == '__main__':
	app.run(debug=False, host='169.63.3.115', port=443,ssl_context=context)
