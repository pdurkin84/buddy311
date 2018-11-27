import ssl
from sanic import Sanic
from sanic.response import json
from sanic_cors import CORS, cross_origin
import re, string
import multiprocessing
import json as jsn
from finetune import Classifier
import os.path

app = Sanic()
CORS(app)

# Once we have workers each (sadly) must load its own model
#model = Classifier.load("/root/combined_model_20181021")
model=None

def loadConfiguration(file):
	with open(file) as json_data_file:
		data=jsn.load(json_data_file)

	# verify mandatory parameters and set defaults
	if data.get('modelfile') == None or not os.path.isfile(data.get('modelfile')):
		print("Unable to find model file, exiting")
		exit(1)
	if data.get('port') == None:
		data['port'] = 31102
	if data.get('hostip') == None:
		data['hostip'] = "0.0.0.0"

	print("Data is: ", data)
	return data

translator = str.maketrans('', '', string.punctuation) # To remove punctuation

# Alex's
def clean_specifics(complaint):
    complaint = re.sub('Request entered through the Web. Refer to Intake Questions for further description.',
                      '', complaint)
    complaint = re.sub('Transfer:.+/[A-Z]+', '', complaint)
    complaint = re.sub('ACCT ', '', complaint)
    complaint = re.sub('RTC ', '', complaint)
    return complaint

def preProcess(complaintStart):
	complaint = clean_specifics(complaintStart)
	complaint = ' '.join([word for word in complaint.split() if word not in cachedStopWords]) # remove stopwords (alex) early on to make 512 limit 
	complaint = complaintStart[:512] # cut to 512 characters max
	complaint = re.sub("\d","", complaint) # remove numbers completely (alex)
	complaint = complaint.lower().translate(translator) # lower case and remove the punctuation
	complaint = re.sub('[^\w\s]', ' ', complaint) # Sub puncuation with space (alex)
	complaint = complaint.strip() # (alex)
	complaint = re.sub(' +', ' ', complaint) # Remove dupe spaces (alex)
	complaint = complaint.replace("\n"," ").strip() # remove starting and trailing white spaces
	if re.search('[a-zA-Z]', complaint) is None:# if there are no letters in the complaint, return empty, will be removed in later processing
		return ""
	complaint = ' '.join([word for word in complaint.split() if word not in cachedStopWords]) # remove stopwords at end after preprocessing (alex) 
	return complaint

@app.route('/', methods=['GET'])
async def testServerAvailability(request):
	print(request)
	return json({'result': 'Server is active'})

@app.route('/buddy311/v0.1/', methods=['POST','GET','OPTIONS'])
async def classifyOpen311Complaint(request):
	global model

	# Check if data provided
	if request.json == None:
		return json({"result", "No data in request"})

	# Check if we have a 311 'description' field
	if request.json.get('description') == None and request.json.get('descriptions') == None:
		return json({'service_code': 'unknown'})

	# If the model is not already loaded then load it
	if model == None:
		model = Classifier(max_length=512, val_interval=3000, verbose = True)
		model = Classifier.load("/root/combined_model_20181021")

	if request.json.get('descriptions') != None:
		processedComplaints = list(map(lambda x: preProcess(x), request.json.get('descriptions')))
		prediction = model.predict(processedComplaints).tolist()
	else:
		print("Doing simple prediction")
		#prediction = model.predict([preProcess(request.json.get('description'))])[0]
		prediction_proba=model.predict_proba([preProcess(request.json.get('description'))])[0]
		print("Probabilities: ", prediction_proba)
		prediction = max(prediction_proba, key=prediction_proba.get)
		# has to be a string otherwise sanic crashes
		prediction_value = str(prediction_proba[prediction])
		print("Top probability: %s, at %s" % (prediction, prediction_value))

	print("Prediction is: ", prediction)

	# If we have a service_code in the incoming request then we assume an Open311 message,
	# so we update the service_code and return the full message.  Otherwise we just send
	# back a new message with the service_code only
	if request.json.get('service_code') == None:
		print("No service code provided, returning one")
		return json({'service_code': prediction, 'service_code_proba': prediction_value})
	else:
		print("Service_code was provided so updating it")
		request.json['service_code'] = prediction
		request.json['service_code_proba'] = prediction_value
		print(request.json)
		return json(request.json)

"""
handle calls from google assistant
"""
@app.route('/v0.1/assistant', methods=['POST','GET','OPTIONS'])
async def processGoogleActionRequest(request):
	global model
	print("Received POST request on google interface")

	# Check if data provided
	if request.json == None:
		return json({"result", "No data in request"})
	some_json = request.json
	if some_json.get('queryResult') == None:
		print("Empty message text")
		return json({'fulfillmentText': 'unknown'})
	queryResult = some_json.get('queryResult')
	if queryResult.get('queryText') == None:
		print("Empty message text")
		return json({'fulfillmentText': 'unknown'})
	newTextDescription = queryResult.get('queryText')
	print("received: ", newTextDescription)
	processedDescription = preProcess(newTextDescription)
	print("pre-processed: ", processedDescription)

	# If the model is not already loaded then load it
	if model == None:
		model = Classifier(max_length=512, val_interval=3000, verbose = True)
		model = Classifier.load("/root/combined_model_20181021")

	# Predict the classification of the text
	prediction = model.predict([processedDescription])

	# Return the result
	print("returning: ", prediction[0])
	return json({'fulfillmentText': prediction[0]})

config = loadConfiguration('buddy311.json')
#context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
#if config.get('cafile') != None:
	#context.load_verify_locations('/etc/ssl/certs/www_buddy311_org.ca-bundle')
#context.load_cert_chain(config.get('crtfile'), keyfile=config.get('keyfile'))

cpu_cores=multiprocessing.cpu_count()
print("CPU count: " ,cpu_cores)
if __name__ == '__main__':
	#app.run(host='0.0.0.0', port=31102,ssl=context, workers=cpu_cores, debug=False)
	#app.run(host=config.get('hostip'), port=int(config.get('port')),ssl=context, workers=cpu_cores, debug=False)
	app.run(host=config.get('hostip'), port=int(config.get('port')),workers=cpu_cores, debug=False)
