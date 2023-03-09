from mqtt_sub import MQTTSubscriber
import psycopg2, psycopg2.pool
from flask import Flask, request, jsonify
import threading 
from concurrent.futures import ThreadPoolExecutor
import signal
import sys
import json
import datetime
import codecs
import urllib.parse
import json
from flask import Response
from geopy.geocoders import Nominatim 
from graphqlclient import GraphQLClient 
from gql.transport.requests import RequestsHTTPTransport
from gql import gql
from gql import Client as TransportClient
from graphql import parse
import requests
# Initialize Flask application
app = Flask(__name__)        

# Connecting to db
# My db stucture: bus <- bus_status -> stop -> stop_event
conn_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host="bus_routes_db",
    port=5432,
    database="bus_data",
    user="ahmettugsuz",
    password="bus_finland",
)


geolocator = Nominatim(user_agent="my_app") # creating a geolocater variable on my app

# Define the base URL for the Nominatim API
base_url = 'https://nominatim.openstreetmap.org/search'

# Setting up the cursor 
cursor = None
conn_key = "poolkey"

# method to get a connection from the pool
def get_connection():
    global cursor
    conn = conn_pool.getconn(key=conn_key)
    cursor = conn.cursor()
    return conn

# Method to release a connection back to the pool
def release_connection(conn):
    conn_pool.putconn(conn=conn, key=conn_key)

# Method to close all connestions in the pool
def close_all_connections():
    conn_pool.closeall()


def start_subscriber():
    """
        Mainly focusing on subscribing to the topic:
        - We only collect the ongoing vehicles, in our case the buses.
        - Geohashlevel is set to: 2, because we dont want the smallest changes at the coordinates
    """

    # Get a connection from the pool
    conn = get_connection()

    # The broker address we want to connect to
    broker_address = "mqtt.hsl.fi" 

    # Topic we want to subscribe to
    topic = "/hfp/v2/journey/ongoing/+/bus/+/+/+/+/+/+/+/2/#" 

    # Creating an instance of MQTTSubscriber class
    subscriber = MQTTSubscriber(broker_address=broker_address, topic=topic, conn_pool=conn_pool, conn_key=conn_key)

    # Start consuming telemetry messages
    subscriber.start()

    # Release the connection back to the pool
    release_connection(conn)

# Threading the subscriber class independently so that the class can run on max 10 threads simultaneously, while also the Flask app can run simultaneously when the app is running
executor_subscriber_class = ThreadPoolExecutor(max_workers=10)
executor_subscriber_class.submit(start_subscriber)




@app.route('/vehicles/<int:vehicle_number>') # By default method = GET to retrieve data, doesen't PUT/POST or change the data
def get_vehicle(vehicle_number: int):
    """
    - Input: vehicle number
    - Returns: Json data about a specific vehicle 

    This method takes in a specific vehicle number and returns all the saved/stored/events information about it. 

    """
    conn = get_connection()
    cursor.execute("""SELECT bus_status.*, stop.*, bus.operator, stop_event.status, stop_event.arrival_time_to_the_stop
    FROM bus_status 
    INNER JOIN stop ON stop.id = bus_status.id
    LEFT JOIN bus ON bus.vehicle_number = bus_status.vehicle_number
    LEFT JOIN stop_event ON stop_event.id = stop.stop_event 
    WHERE bus_status.vehicle_number=%s""", (vehicle_number,))

    results = cursor.fetchall() # fetching the result from the query

    if len(results) == 0:
        # If the given vehicle number is not found
        return jsonify({"message": "No vehicle found with the given vehicle number"})

    else:
        vehicle_list = []
        for result in results:
            vehicle_dict = {
                "vehicle_number" : result[1],
                "route_number": result[4],
                "utc_timestamp": str(result[3]),
                "current_location": result[5],
                "destination": result[9],
                "next_stop": result[13],
                "operator": result[16],
                "status": result[17],
                "arrival_time_to_the_stop": str(result[18])
            }
            js = json.dumps(vehicle_dict, ensure_ascii=False)
            vehicle_list.append(js)

        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(vehicle_list) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False).encode('utf-8'), mimetype='application/json; charset=utf-8')


@app.route('/locations') # By default GET to retrieve data, doesen't PUT/POST or change the data
def get_all_bus_locations():
    """
    - Input: None
    - Output: Returns updated bus json (with information, current_location etc.)

    This method returns all last updated bus information about their locations, tsi, route number, last updated timestamp, destination, operator for each bus in whole finland.
    """
    conn = get_connection()
    cursor.execute(""" 
        SELECT bs.*, bus.operator
        FROM bus_status bs
        LEFT JOIN bus ON bus.vehicle_number = bs.vehicle_number
        INNER JOIN (
            SELECT vehicle_number, MAX(tsi) AS max_tsi
            FROM bus_status
            GROUP BY vehicle_number
        ) bs_max ON bs.vehicle_number = bs_max.vehicle_number AND bs.tsi = bs_max.max_tsi;
    """)
    results = cursor.fetchall()
    counter_result = 0
    if len(results) == 0:
        return jsonify({"message": "No vehicle found"})
    else:
        bus_data = []
        for result in results:
            counter_result += 1
            bus_dict = {
                "vehicle_number" : result[1],
                "tsi": result[2],
                "route_number": result[4],
                "utc_timestamp": str(result[3]),
                "current_location": result[5],
                "destination": result[9],
                "operator": result[10]
            }
            json_bus = json.dumps(bus_dict, ensure_ascii=False)
            bus_data.append(json_bus)
        print(counter_result, " bus data found")
        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False).encode('utf-8'), mimetype='application/json; charset=utf-8')
    
@app.route('/locations/next_stop') # By default GET to retrieve data, doesen't PUT/POST or change the data
def last_location_next_stop():
    """
    This method get the last data about each bus and show their current location with the next stop, including operator, route_number, utc timestamp for when updated, status if any, and arrival_time if any
    - Input: none
    - Output: Return json data about last known locations with their next stop
    """
    get_connection()
    cursor.execute("""
        SELECT bs.*, stop.*, bus.operator, stop_event.status, stop_event.arrival_time_to_the_stop
        FROM bus_status AS bs
        LEFT JOIN bus ON bus.vehicle_number = bs.vehicle_number
        LEFT JOIN stop ON stop.id = bs.stop_id
        LEFT JOIN stop_event ON stop_event.id = stop.stop_event
        INNER JOIN (
            SELECT vehicle_number, MAX(tsi) AS max_tsi
            FROM bus_status
            GROUP BY vehicle_number
        ) bs_max ON bs.vehicle_number = bs_max.vehicle_number AND bs.tsi = bs_max.max_tsi;
        """)
    results = cursor.fetchall()
    if len(results) == 0:
        return jsonify({"message": "No vehicle found"})
    else: 
        bus_data = []
        for result in results:
            bus_dict = {
                "vehicle_number" : result[1],
                "route_number": result[4],
                "utc_timestamp": str(result[3]),
                "current_location": result[5],
                "destination": result[9],
                "next_stop": result[13],
                "operator": result[16],
                "status": result[17],
                "arrival_time_to_the_stop": str(result[18])
            }
            json_bus = json.dumps(bus_dict, ensure_ascii=False)
            bus_data.append(json_bus)

        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False).encode('utf-8'), mimetype='application/json; charset=utf-8')


# This method is doing nearly the same as the method below buses_within_radius(),
#   the difference is that i would prefer to use a method like this on my frontend to ensure i can pass the location address with json to this method 
@app.route('/buses_near_me', methods=['GET'])
def buses_near_me():
    """ 
    - input: street and city name to get the location of the user, and a radius to show bus near user
    - output: json data about the buses near the user  
    This function takes as input a street and city name to determine the user's location, as well as a radius to display buses located near the user. 
    The output is a JSON object containing data about the buses in the vicinity of the user.

    """
    get_connection()

    data = request.get_json()

    # Define the query parameters
    params = {
        'q': data['location'],
        'format': 'jsonv2'
    }

    # Send a GET request to the API
    response = requests.get(base_url, params=params)

    # if the request was successful
    if response.ok:
        # Parse the response JSON to extract the latitude and longitude
        data = response.json()[0]
        lat = data['lat']
        lon = data['lon']
        radius = data['radius']

                # Selecting the latest 'tsi' for each vehicle number, within a given radius
        cursor.execute(""" 
            SELECT * FROM bus_status AS bs
            INNER JOIN (
                SELECT vehicle_number, MAX(tsi) AS max_tsi
                FROM bus_status
                GROUP BY vehicle_number
            ) bs_max ON bs.vehicle_number = bs_max.vehicle_number AND bs.tsi = bs_max.max_tsi
            WHERE earth_distance(ll_to_earth(latitude, longitude), ll_to_earth(%s, %s)) <= %s
        """, (lat, lon, radius))
        results = cursor.fetchall()


        if len(results) == 0:
            return jsonify({"message": "No bus found"})
        else:
            bus_data = []
            for result in results:
                bus_dict = {
                    "vehicle_number" : result[1],
                    "route_number": result[4],
                    "utc_timestamp": str(result[3]),
                    "current_location": result[5],
                    "destination": result[9],
                }
                json_bus = json.dumps(bus_dict, ensure_ascii=False)
                bus_data.append(json_bus)
                    # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False).encode('utf-8'), mimetype='application/json; charset=utf-8')
    else:
        # If the request was not successful, print the error message
        print(f"Error: {response.status_code} - {response.reason}")


# This method allows ut to define radius and the location passed in to the url, its just a variation of the buses_within_radius()
# This is also easier to test, results can be shown easier   
@app.route('/buses_within_radius/<string:street>/<string:city>/<int:radius>')
def buses_within_radius(street, city, radius):
    """ 
    - input: street and city name to get the location of the user, and a radius to show bus near user
    - output: json data about the buses near the user  
    This function takes as input a street and city name to determine the user's location, as well as a radius to display buses located near the user. 
    The output is a JSON object containing data about the buses in the vicinity of the user.

    """

    conn = get_connection()

    # Define the query parameters
    params = {
        'q': f"{city}, {street}",
        'format': 'jsonv2'
    }

    # Send a GET request to the API
    response = requests.get(base_url, params=params)

    # if the request was successful
    if response.ok:
        # Parse the response JSON to extract the latitude and longitude
        data = response.json()[0]
        lat = data['lat']
        lon = data['lon']
        
        # Selecting the latest 'tsi' for each vehicle number, within a given radius
        try:
            cursor.execute(""" 
                SELECT bs.*, bus.operator, stop.stop_name FROM bus_status AS bs
                LEFT JOIN bus ON bus.vehicle_number = bs.vehicle_number
                LEFT JOIN stop ON stop.id = bs.stop_id
                INNER JOIN (
                    SELECT vehicle_number, MAX(tsi) AS max_tsi
                    FROM bus_status 
                    GROUP BY vehicle_number
                ) bs_max ON bs.vehicle_number = bs_max.vehicle_number AND bs.tsi = bs_max.max_tsi
                WHERE earth_distance(ll_to_earth(bs.latitude, bs.longitude), ll_to_earth(%s, %s)) <= %s
            """, (lat, lon, radius))
            results = cursor.fetchall()
        except Exception as e:
            # Return an error message in JSON format
            error_message = {"error": str(e)}
            return jsonify(error_message), 500

        if len(results) == 0:
            return jsonify({"message": "No bus found"})
        else:
            bus_data = []
            for result in results:
                bus_dict = {
                    "vehicle_number" : result[1],
                    "route_number": result[4],
                    "utc_timestamp": str(result[3]),
                    "current_location": result[5],
                    "destination": result[9],
                    "operator": result[10],
                    "next_stop": result[11]
                }
                json_bus = json.dumps(bus_dict, ensure_ascii=False)
                bus_data.append(json_bus)
                    # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False).encode('utf-8'), mimetype='application/json; charset=utf-8')
    else:
        # If the request was not successful, print the error message
        print(f"Error: {response.status_code} - {response.reason}")


    
# Define a signal handler for SIGINT (Ctrl+C)
def sigint_handler(signal, frame):
    print("Received SIGINT, stopping Flask app... You may need to click Ctrl+C again to stop both subscriber and Flask programs")
    # Perform any cleanup necessary (e.g. closing DB connections, releasing the threads ..)
    # Stop the Flask app
    # Making sure to close the cursor 
    if not cursor.closed: 
        cursor.close()
        
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, sigint_handler)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



