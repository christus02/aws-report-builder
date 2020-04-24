#!/usr/bin/python

import boto3
from prettytable import PrettyTable
from flask import Flask, request, send_file, redirect, url_for, jsonify
import datetime
import pytz
import threading
import sys
from urllib import unquote_plus

app = Flask(__name__)
FLASK_PORT = 9001

# Decorator for threading
#def threaded(f, daemon=False):
#    import Queue
#
#    def wrapped_f(q, *args, **kwargs):
#        '''this function calls the decorated function and puts the 
#        result in a queue'''
#        ret = f(*args, **kwargs)
#        q.put(ret)
#
#    def wrap(*args, **kwargs):
#        '''this is the function returned from the decorator. It fires off
#        wrapped_f in a new thread and returns the thread object with
#        the result queue attached'''
#
#        q = Queue.Queue()
#
#        t = threading.Thread(target=wrapped_f, args=(q,)+args, kwargs=kwargs)
#        t.daemon = daemon
#        t.start()
#        t.result_queue = q
#        return t
#
#    return wrap

def get_all_regions():
    ec2 = boto3.client('ec2')
    res = ec2.describe_regions()
    ret = []
    for region in res['Regions']:
        ret.append(region['RegionName'])

    return ret

@app.route('/server/status')
def status_check():
    return "The AWS Query Server is UP and RUNNING"

def convert_to_table(heading, values):
    table = PrettyTable(heading)
    table.format = True
    for row in values:
        table_row = []
        for i in range(0, len(heading)):
            table_row.append(row[heading[i]])
        table.add_row(table_row)

    return (table)
        

#@threaded
def get_running_instances_from_region(region, uptime=0, state='running'):
    # Return Data Structure - List of Dictionaries - [{instance1}, {instance2}]
   data = []
   ec2 = boto3.client('ec2', region_name=region)
   res = ec2.describe_instances(
             Filters=[
                 {
                  'Name': 'instance-state-name',
                  'Values': [state]
                 }
             ]
             )

   for reservation in res['Reservations']:
       for instance in reservation['Instances']:
           instance_data = {}
           append = True
           # Convert Launch time to days
           instance_data['instance_uptime'] = calculate_instance_age(instance['LaunchTime'])
           if ((uptime != 0) and (not instance_data['instance_uptime'] <= uptime)):
               append = False
               continue;
           else:
               instance_data['instance_uptime'] = str(calculate_instance_age(instance['LaunchTime']))
           instance_data['instance_id'] = instance['InstanceId']
           instance_data['instance_type'] = instance['InstanceType']
           instance_data['instance_state'] = instance['State']['Name']
           instance_data['instance_vpc_id'] = instance['VpcId']
           instance_data['instance_az'] = instance['Placement']['AvailabilityZone']
           instance_data['instance_name'] = ""
           try:
               for tag in instance['Tags']:
                   if tag['Key'] == "Name":
                       instance_data['instance_name'] = tag['Value']
           except:
               #Either no TAG or no instance itself
               pass
       if append:
           data.append(instance_data)

   return (data)

@app.route("/ec2/<state>/<region>/<uptime>")
def wrapped_ec2(state, region, uptime):
    return get_ec2({'state':state, 'region':region, 'uptime':uptime})
@app.route("/ec2")
def get_ec2(input_data={}):

    if input_data:
        region = unquote_plus(input_data['region'])
        state = unquote_plus(input_data['state'])
        uptime = unquote_plus(input_data['uptime'])
    else:
        # Parsing the Query String
        region = unquote_plus(request.args.get('region', "all"))
        state = unquote_plus(request.args.get('state', 'running'))
        uptime = int(unquote_plus(request.args.get('uptime', '0')))

    if region == "all":
        all_regions = get_all_regions()
    else: 
        all_regions = []
        all_regions.append(region)

    ret_str = ""
    ret_str = ret_str + style_string()
    for reg in all_regions:
        #thread_data = get_running_instances_from_region(reg, uptime, state)
        #data = thread_data.result_queue.get()
        data = get_running_instances_from_region(reg, uptime, state)

        if len(data) >= 1:
            # Printing to Table
            table = convert_to_table(["instance_id", "instance_name", "instance_type", "instance_state", "instance_uptime", "instance_vpc_id", "instance_az"], data)
            # Print to HTML
            ret_str = ret_str + "<h2> Region: "+reg+" </h2>"
            ret_str = ret_str + table.get_html_string(attributes={"id":"aws", "class":"aws", "name":"aws"})
        else:
            ret_str = ret_str + "<h2> Region: "+reg+" </h2><h4> No Instances in this Region </h4>"

    return ret_str


def calculate_instance_age(launch_time):

    my_time_zone = pytz.timezone('Asia/Kolkata')
    current_time = my_time_zone.localize(datetime.datetime.now())
    
    diff = current_time - launch_time
    # This returns days in int
    # Example: 249 days
    return diff.days

def style_string():

    style_string = '''<style>
#aws {
  font-family: "Trebuchet MS", Arial, Helvetica, sans-serif;
  border-collapse: collapse;
  width: 100%;
}

#aws td, #customers th {
  border: 1px solid #ddd;
  padding: 8px;
}

#aws tr:nth-child(even){background-color: #f2f2f2;}

#aws tr:hover {background-color: #ddd;}

#aws th {
  padding-top: 12px;
  padding-bottom: 12px;
  text-align: left;
  background-color: #4CAF50;
  color: white;
}
</style>'''
    return style_string

def head_string():
    head_string = '''
<html>
<head>
  <title>AWS Report Builder</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.4.1/css/bootstrap.min.css">
  <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.4.1/jquery.min.js"></script>
  <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.4.1/js/bootstrap.min.js"></script>
</head>
'''
    return head_string

def jumbotron():
    jumbotron_string = '''
<body>
<div class="jumbotron text-center">
    <h1>AWS Report Builder</h1>
    <p>You can query AWS Instances of your account from this portal</p>
</div>
<br>
'''
    return jumbotron_string

def urls():
    ret_str = ""
    ret_str = '''
<div class="container">
    <div class="col-sm-6">
        <div class="panel panel-default">
        <div class = "panel-heading"><h3 class = "panel-title">Available Reports</h3></div>
        <div class="panel-body">
<a href=%s>Instances Running in ap-south-1</a>
<br>
<a href=%s>Instances Running in us-east-1</a>
<br>
<a href=%s>Instances Running for last 7 days in ALL REGIONS</a>
<br>
<a href=%s>Stopped Instances in ap-south-1</a>
<br>
</div></div></div></div></div>
''' % (url_for('get_ec2', state='running', region='ap-south-1'),
       url_for('get_ec2', state='running', region='us-east-1'),
       url_for('get_ec2', state='running', region='ap-south-1', uptime='7'),
       url_for('get_ec2', state='stopped', region='ap-south-1'),
       )
    return ret_str

@app.route("/")
def landing():
    return head_string() + jumbotron() + urls() + "</body></html>"

if __name__ == '__main__':
    try: 
        app.run(host='0.0.0.0', port=FLASK_PORT)
    except (KeyboardInterrupt, SystemExit):
        print ("Exiting on Keyboard Interrupt")
        sys.exit()
    except:
        print ("Exiting on exception")
        sys.exit()
