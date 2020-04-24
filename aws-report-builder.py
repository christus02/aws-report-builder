#!/usr/bin/python

import boto3
from prettytable import PrettyTable
from flask import Flask, request, send_file, redirect, url_for, jsonify
import datetime
import pytz

app = Flask(__name__)
FLASK_PORT = 9001

def get_all_regions():
    ec2 = boto3.client('ec2')
    res = ec2.describe_regions()
    ret = []
    for region in res['Regions']:
        ret.append(region['RegionName'])

    return ret

@app.route('/')
def status_check():
    return "The AWS Query Server is UP and RUNNING"

@app.route("/ec2/running/<region>", methods = ['GET'])
@app.route("/ec2/running", methods = ['GET'])
def print_running_instance_from_region(region='ap-south-1'):

   ret_str = ""
   data = get_running_instances_from_region(region)
   if len(data) >= 1:
       # Printing to Table
       table = convert_to_table(["instance_id", "instance_name", "instance_type", "instance_state", "instance_uptime", "instance_vpc_id", "instance_az"], data)
       # Print to HTML
       #ret_str = ret_str + "<h2> Instances from Region: "+region+" </h2>"
       ret_str = ret_str + "<h2> Region: "+region+" </h2>"
       ret_str = ret_str + table.get_html_string()
   else:
       ret_str = "<h2> Region: "+region+" </h2><h4> No Instances in Running State in this Region </h4>"
      
   return ret_str

@app.route("/ec2/running/all-regions")
def print_running_instances_from_all_regions():

    ret_str = ""
    all_regions = get_all_regions()
    for region in all_regions:
        region_data = print_running_instance_from_region(region)
        ret_str = ret_str + region_data

    return ret_str

def convert_to_table(heading, values):
    table = PrettyTable(heading)
    table.format = True
    for row in values:
        table_row = []
        for i in range(0, len(heading)):
            table_row.append(row[heading[i]])
        table.add_row(table_row)

    return (table)
        

def get_newly_launched_instances(region):
   pass

def get_running_instances_from_region(region):
    # Return Data Structure - List of Dictionaries - [{instance1}, {instance2}]
   data = []
   ec2 = boto3.client('ec2', region_name=region)
   res = ec2.describe_instances(
             Filters=[
                 {
                  'Name': 'instance-state-name',
                  'Values': ['running']
                 }
             ]
             )
   for reservation in res['Reservations']:
       for instance in reservation['Instances']:
           instance_data = {}
           instance_data['instance_id'] = instance['InstanceId']
           instance_data['instance_type'] = instance['InstanceType']
           instance_data['instance_state'] = instance['State']['Name']
           # Convert Launch time to days
           instance_data['instance_uptime'] = str(calculate_instance_age(instance['LaunchTime']))
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
       data.append(instance_data)

   return (data)

def calculate_instance_age(launch_time):

    my_time_zone = pytz.timezone('Asia/Kolkata')
    current_time = my_time_zone.localize(datetime.datetime.now())
    
    diff = launch_time - current_time
    # This returns days in int
    # Example: -249 days
    return diff.days

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=FLASK_PORT)
