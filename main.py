import json
import app
import os
from dotmap import DotMap

pd_source = os.environ['PD_SOURCE'] or "aws.partner/pagerduty.com/event_bus_name"

def lambda_handler(event, context):
 
    print("AWS PAYLOAD: ", event)
    req = DotMap(event)
    
    if(req.source and req.source == pd_source):
        
        print("PAGERDUTY PAYLOAD: ", req.detail)
        print("PAGERDUTY DOTMAP EVENT: ", req.detail.event)
        #app.app_test(req.detail)
        
        if(req.detail.event == 'incident.custom'):
            app.start_zoom(req.detail)

    elif(req.body):
        
        print("API GATEWAY BODY: ", req.body)
        zoomDetails = DotMap(json.loads(event["body"]))
        print("ZOOM EVENT: ", zoomDetails.event)
        
        #app.app_test(zoomDetails)
        app.logZoomEvent(zoomDetails)
        
    else:
        print("UNKNOWN EVENT: ", event)
    
    return {
        'statusCode': 200,
    }
