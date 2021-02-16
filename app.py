import time
import calendar
import jwt
import requests
import re
import os
from flask import Flask, request, Response
import json
from dotmap import DotMap
import pd

import pprint
pp = pprint.PrettyPrinter(indent=4)

pd_key = os.environ['PD_KEY'] or "Set your PD_KEY environment variable to a PD API token"
from_email = os.environ['FROM_EMAIL'] or "Set your FROM_EMAIL environment variable to the login email of a PD user"
zoom_key = os.environ['ZOOM_KEY'] or "Set your ZOOM_KEY environment variable to a Zoom REST API access key"
zoom_secret = os.environ['ZOOM_SECRET'] or "Set your ZOOM_SECRET environment variable to your Zoom REST API client secret"
zoom_userid  = os.environ['ZOOM_USERID'] or "Set your ZOOM_USERID environment variable to your Zoom REST User ID"

app = Flask(__name__)

def zoom_token():
		zoom_jwt_payload = { 'iss': zoom_key, 'exp': calendar.timegm(time.gmtime()) + 36000 }
		zoom_token = jwt.encode(zoom_jwt_payload, zoom_secret)
		return zoom_token.decode("utf-8")
		

@app.route("/", methods=['POST'])
def logZoomEvent(req):
	print("LOGGING ZOOM EVENT: ", req.event)
	
	if req.event == 'meeting.participant_joined' or req.event == 'meeting.participant_left' or req.event == 'meeting.started' or req.event == 'meeting.ended':
		
		print("ZOOM EVENT RECGONISED: ", req.event)
		
		meeting_id = req.payload.object.id
		meeting_topic = req.payload.object.topic
		
		action = req.event.split('.')[1]
		if "_" in action:
			print("ZOOM EVENT ACTION: ", action)
			action = action.split('_')[1]
			
		user_name = req.payload.object.participant.user_name
		user_id = req.payload.object.participant.user_id
		
		print("ZOOM EVENT USER: ", user_name, " ID: ", user_id)
		
		zoom_req = requests.Request(method="get", 
			url=f"https://api.zoom.us/v2/users/{user_id}", 
			headers={"Authorization": f"Bearer {zoom_token()}"})
			
		prepped = zoom_req.prepare()
		response = requests.Session().send(prepped)
		
		user_email = response.json().get("email");
		print("ZOOM RESPONSE EMAIL: ", user_email)
		
		if action == 'started' or action == 'ended':
			note = f'Zoom meeting {meeting_id} ({meeting_topic}) {action}'
		else:
			note = f'{user_name} ({user_email}) {action} Zoom meeting {meeting_id} ({meeting_topic})'

		print("ZOOM NOTE : ", note)
		incidents = pd.fetch(api_key=pd_key, endpoint="incidents", params={"statuses[]": ["triggered", "acknowledged"], "include[]": ["metadata"]})
		conf_bridges = [{"id": incident.get("id"), "metadata": incident.get("metadata")} for incident in incidents if incident.get("metadata")]

		print("ZOOM MEETING ID : ", meeting_id)
		print("PD CONF BRIDGES : ", conf_bridges)
		for bridge in conf_bridges:
			
			print("PD CONF URL : ", bridge["metadata"].get("conference_url"))
			
			if bridge["metadata"].get("conference_url"):
				conf = re.findall("[\d]+\?", bridge["metadata"]["conference_url"].replace('-', ''))[0][:-1]
				print("PD CONF : ", conf)
				if (meeting_id == conf):
					print(f'I should put this note on incident {bridge["id"]} because conference url is {bridge["metadata"]["conference_url"]}')
					r = pd.add_note(api_key=pd_key, incident_id=bridge["id"], from_email=from_email, note=note)

			elif bridge["metadata"].get("conference_number"):
				conf = re.findall("[\d]+", bridge["metadata"]["conference_number"].replace('-', ''))[-1]
				print("PD BRIDGE : ", conf)
				if (meeting_id == conf):
					print(f'I should put this note on incident {bridge["id"]} because conference number is {bridge["metadata"]["conference_number"]}')
					r = pd.add_note(api_key=pd_key, incident_id=bridge["id"], from_email=from_email, note=note)
					
	return "", 200

@app.route("/start", methods=['POST'])
def start_zoom(req):
	incident_id = req.incident.id
	incident_title = req.incident.title
	incident_number = req.incident.incident_number
	requester_id = req.log_entries[0].agent.id
	requester_name = req.log_entries[0].agent.summary
	url = f"https://api.zoom.us/v2/users/{zoom_userid}/meetings"

	topic = f'[{incident_number}] {incident_title}'
	print(f'start zoom requested on {topic} by {requester_id} ({requester_name})')

	data = {
		"type": 1,
		"topic": topic
	}
	req = requests.Request(
		method='POST',
		url=url,
		headers={"Authorization": f"Bearer {zoom_token()}"},
		json=data
	)

	prepped = req.prepare()
	response = requests.Session().send(prepped)
	res = DotMap(response.json())

	if res.join_url:
		join_url = res.join_url
	else:
		join_url = ""
	
	if res.settings.global_dial_in_numbers[0].number:
		join_tel = f"{res.settings.global_dial_in_numbers[0].number},,{res.id}#"
	else:
		join_tel = ""
	
	print(f'created meeting {join_url} for incident {topic}')
	
	add_conf = {
		"requester_id": requester_id,
		"incidents": [
			{
				"id": incident_id,
				"type": "incident_reference",
				"metadata":  {
					"conference_url": join_url,
					"conference_number": join_tel
				}
			}
		]
	}
	response = pd.request(api_key=pd_key, endpoint="/incidents", method="PUT", data=add_conf, addheaders={"From": from_email})

	return "", 200


def app_test(req):

# PD TEST
#	print("PD TEST")
#	print("incident_id = ", req.incident.id)
#	print("incident_title = ", req.incident.title)
#	print("incident_number = ", req.incident.incident_number)
#	print("requester_id = ", req.log_entries[0].agent.id)
#	print("requester_name = ", req.log_entries[0].agent.summary)

# ZOOM TEST
	if req.event == 'meeting.participant_joined' or req.event == 'meeting.participant_left' or req.event == 'meeting.started' or req.event == 'meeting.ended':
		print("ZOOM EVENT ", req.event)
		print("ZOOM EVENT ID ", req.payload.object.id)

	return "", 200
