#!/usr/bin/python

import boto3
from prettytable import PrettyTable
from flask import Flask, request, send_file, redirect, url_for, jsonify
import datetime
import pytz
import threading
import sys

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

def region_to_name(region):
    region_to_name_mapping = {
        "eu-north-1":"Europe (Stockholm)",
        "ap-south-1":"Asia Pacific (Mumbai)",
        "eu-west-3":"Europe (Paris)",
        "eu-west-2":"Europe (London)",
        "eu-west-1":"Europe (Ireland)",
        "ap-northeast-2":"Asia Pacific (Seoul)",
        "me-south-1":"Middle East (Bahrain)",
        "ap-northeast-1":"Asia Pacific (Tokyo)",
        "sa-east-1":"South America (Sao Paulo)",
        "ca-central-1":"Canada (Central)",
        "ap-southeast-1":"Asia Pacific (Singapore)",
        "ap-southeast-2":"Asia Pacific (Sydney)",
        "eu-central-1":"Europe (Frankfurt)",
        "us-east-1":"US East (N. Virginia)",
        "us-east-2":"US East (Ohio)",
        "us-west-1":"US West (N. California)",
        "us-west-2":"US West (Oregon)",
    }
    if region in region_to_name_mapping.keys():
        return region_to_name_mapping[region]
    else:
        return None

def table_heading_mapping(heading):
    table_heading_mapping = {
        "instance_id": "Instance ID", 
        "instance_name": "Instance Name",
        "instance_type": "Instance Size",
        "instance_state": "Instance State",
        "instance_uptime": "Instance Uptime",
        "instance_vpc_id": "VPC ID",
        "instance_az": "AZ",
    }
    if heading in table_heading_mapping.keys():
        return table_heading_mapping[heading]
    else:
        return None

@app.route('/server/status')
def status_check():
    return "The AWS Query Server is UP and RUNNING"

def convert_to_table(heading, values):
    new_heading = []
    for head in heading:
        new_heading.append(table_heading_mapping(head))
    table = PrettyTable(new_heading)
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

@app.route("/ec2/<state>/<region>/<uptime>", methods = ['GET'])
def wrapped_ec2(state, region, uptime):
    input_data = {'state':state, 'region':region, 'uptime':uptime}
    return get_ec2(input_data)
@app.route("/ec2", methods = ['POST', 'GET'])
def get_ec2(input_data={}):

    if request.method == 'POST':
        region = request.form.get('region')
        state = request.form.get('state')
        uptime = request.form.get('uptime')
        if uptime == "":
            uptime = 0
        else:
            uptime = int(uptime)
    else: 
        if input_data:
            print ("Got Input Data")
            region = input_data['region']
            state = input_data['state']
            uptime = input_data['uptime']
            print (region, state, uptime)
        else:
            # Parsing the Query String
            region = request.args.get('region', "all")
            state = request.args.get('state', 'running')
            uptime = int(request.args.get('uptime', '0'))

    if region == "all":
        all_regions = get_all_regions()
    else: 
        all_regions = []
        all_regions.append(region)

    ret_str = ""
    ret_str = ret_str + head_string() + style_string()
    ret_str = ret_str + '<div class="container">'
    for reg in all_regions:
        #thread_data = get_running_instances_from_region(reg, uptime, state)
        #data = thread_data.result_queue.get()
        data = get_running_instances_from_region(reg, uptime, state)

        if len(data) >= 1:
            # Printing to Table
            table = convert_to_table(["instance_id", "instance_name", "instance_type", "instance_state", "instance_uptime", "instance_vpc_id", "instance_az"], data)
            # Print to HTML

            ret_str = ret_str + '''
            <div class="panel panel-default">
            <div class = "panel-heading text-center"><h3 class = "panel-title">Region: %s</h3></div>
            <div class="panel-body">%s</div></div></div>''' % (region_to_name(reg), table.get_html_string(attributes={"id":"aws", "class":"aws", "name":"aws"}))

            #ret_str = ret_str + "<h2> Region: "+region_to_name(reg)+" </h2>"
            #ret_str = ret_str + table.get_html_string(attributes={"id":"aws", "class":"aws", "name":"aws"})
        else:
            ret_str = ret_str + '''
            <div class="panel panel-default">
            <div class = "panel-heading text-center"><h3 class = "panel-title">Region: %s</h3></div>
            <div class="panel-body text-center">%s</div></div></div>''' % (region_to_name(reg), "<h4> No Instances in this Region </h4>")
            #ret_str = ret_str + "<h2> Region: "+region_to_name(reg)+" </h2><h4> No Instances in this Region </h4>"

    ret_str = ret_str + '</div></body></html>'
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
    <div class="row">
    <div class="col-sm-6">
        <div class="panel panel-default">
        <div class = "panel-heading text-center"><h3 class = "panel-title">Pre Built Reports</h3></div>
        <div class="panel-body">
        <a class="btn btn-light" href="%s" role="button">Instances Running in Asia Pacific (Mumbai)</a>
        <br>
        <a class="btn btn-light" href="%s" role="button">Instances Running in US East (N. Virginia)</a>
        <br>
        <a class="btn btn-light" href="%s" role="button">Instances Running for last 7 days in ALL REGIONS</a>
        <br>
        <a class="btn btn-light" href="%s" role="button">Stopped Instances in Asia Pacific (Mumbai)</a>
        </div></div></div>
    <div class="col-sm-6">
        <div class="panel panel-default">
        <div class = "panel-heading text-center"><h3 class = "panel-title">Custom Report</h3></div>
        <div class="panel-body">
        <form action="%s" method="POST">
    <div class="form-group>
      <label for="state">EC2 Instance State:</label>
      <select class="form-control" id="state" name="state">
        <option value="running">Running</option>
        <option value="stopped">Stopped</option>
      </select>
    </div>
    <div class="form-group>
      <label for="region">EC2 Instance Region:</label>
      <select class="form-control" id="region" name="region">
        <option value="all">All Regions</option>
        <option value="eu-north-1">Europe (Stockholm)</option>
        <option value="ap-south-1">Asia Pacific (Mumbai)</option>
        <option value="eu-west-3">Europe (Paris)</option>
        <option value="eu-west-2">Europe (London)</option>
        <option value="eu-west-1">Europe (Ireland)</option>
        <option value="ap-northeast-2">Asia Pacific (Seoul)</option>
        <option value="me-south-1">Middle East (Bahrain)</option>
        <option value="ap-northeast-1">Asia Pacific (Tokyo)</option>
        <option value="sa-east-1">South America (Sao Paulo)</option>
        <option value="ca-central-1">Canada (Central)</option>
        <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
        <option value="ap-southeast-2">Asia Pacific (Sydney)</option>
        <option value="eu-central-1">Europe (Frankfurt)</option>
        <option value="us-east-1">US East (N. Virginia)</option>
        <option value="us-east-2">US East (Ohio)</option>
        <option value="us-west-1">US West (N. California)</option>
        <option value="us-west-2">US West (Oregon)</option>
      </select>
    </div>
    <div class="form-group>
      <label for="uptime">EC2 Instance UP Since (days):</label>
      <input type="text" class="form-control floatNumber" id="uptime", name="uptime">
    </div>
    <br>
    <div class="text-center">
    <button type="submit" class="btn btn-primary">Run Query</button>
    </div>
  </form>
        </div></div></div>
    </div></div>
</div></div>
''' % (url_for('wrapped_ec2', state='running', region='ap-south-1', uptime='0'),
       url_for('get_ec2', state='running', region='us-east-1'),
       url_for('wrapped_ec2', state='running', region='all', uptime='7'),
       url_for('get_ec2', state='stopped', region='ap-south-1'),
       url_for('get_ec2'),
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
