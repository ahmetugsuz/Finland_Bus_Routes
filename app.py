from mqtt_sub import MQTTSubscriber
import psycopg2, psycopg2.pool
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor
import signal
import sys
import json
import logging
import json
from flask import Response
from geopy.geocoders import Nominatim 
from geopy.extra.rate_limiter import RateLimiter
from graphql import parse
import requests
import time
from retrying import retry
from cleanup.cleanup import cleanup_in_progress
from opencage.geocoder import OpenCageGeocode
# Initialize Flask application
app = Flask(__name__)        

def connect_to_db(max_retries=0):
    # Connecting to db
    try:
        conn_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host="db",
                port=5432,
                database="bus_data",
                user="ahmettugsuz",
                password="bus_finland",
        )
        return conn_pool
    except Exception as e:
        if max_retries < 1:
            print("Retrying db connection..")
            time.sleep(2)
            # Corrected recursive call
            return connect_to_db(max_retries + 1)

        print(f"Error connecting to the database: {e}")
        return None

conn_pool = connect_to_db()

# Setting up the cursor 
cursor = None
conn_key = "poolkey"


# Create a logger instance
logger = logging.getLogger('application_logger')

# Configure the logging settings
logger.setLevel(logging.INFO)  # Set the log level (INFO, WARNING, ERROR, etc.)

# Create a file handler to write logs to a file
file_handler = logging.FileHandler('application.log')
file_handler.setLevel(logging.INFO)

# Create a console handler to print logs to the terminal
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Define the log message format
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# method to get a connection from the pool
def get_connection():
    time.sleep(0.1)
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
    while not cleanup_in_progress: # if cleanup of the database is not in progress
        # Get a connection from the pool
        #logger.info("Time between threads accumulation is 1 sec.")
        time.sleep(0.01)
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
    if cleanup_in_progress:
        logger.info("--- Pausing Application Server to collect data from broker ---")


def start_threads():
    time.sleep(5)
    #logger.info("The Threads getting ready to be executed ..")
    # Threading the subscriber class independently so that the class can run on max 10 threads simultaneously, while also the Flask app can run simultaneously when the app is running
    executor_subscriber_class = ThreadPoolExecutor(max_workers=1)
    #executor_subscriber_class.daemon = True 
    executor_subscriber_class.submit(start_subscriber)



@app.route('/locations') # By default GET to retrieve data
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
        ) bs_max ON bs.vehicle_number = bs_max.vehicle_number AND bs.tsi = bs_max.max_tsi
        ORDER BY bs.tsi DESC
        LIMIT 300
        ;
    """)


    logger.info("Syncing requested data for locations to JSON API ...")
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

        logger.info("{} bus data retrieved from location fetch".format(counter_result))
        print(' ')
        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False, indent=4).encode('utf-8'), mimetype='application/json; charset=utf-8')
    

@app.route('/locations/next_stop') # By default GET to retrieve data, doesen't PUT/POST or change the data
def last_location_next_stop():
    """
    This method get the last data about each bus and show their current location with the next stop, including operator, route_number, utc timestamp for when updated, status if any, and arrival_time if any
    - Input: none
    - Output: Return json data about last known locations with their next stop
    """
    logger.info("Syncing data for next stop to JSON API ...")
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
        ) bs_max ON bs.vehicle_number = bs_max.vehicle_number AND bs.tsi = bs_max.max_tsi
        ORDER BY bs.tsi DESC
        LIMIT 300
        ;
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
                "next_stop": result[13],
                "operator": result[16],
                "status": result[17],
                "arrival_time_to_the_stop": str(result[18]),
            }
            json_bus = json.dumps(bus_dict, ensure_ascii=False)
            bus_data.append(json_bus)

        logger.info("{} bus data retrieved from location fetch with next stop".format(counter_result))
        print(' ')

        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False, indent=4).encode('utf-8'), mimetype='application/json; charset=utf-8')

   

@app.route('/locations/logger') 
def bus_logger():
    """
    This method logs the data about each bus and show their location and all data related, logged into the db, including operator, route_number, utc timestamp for when updated, status if any, and arrival_time if any
    - Input: none
    - Output: Return json data about last known locations with their next stop
    """
    logger.info("Syncing data for locations logger to JSON API ...")
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
        ) bs_max ON bs.vehicle_number = bs_max.vehicle_number 
        ORDER BY bs.tsi DESC
        LIMIT 1000
        ;
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
                "next_stop": result[13],
                "operator": result[16],
                "status": result[17],
                "arrival_time_to_the_stop": str(result[18]),
            }
            json_bus = json.dumps(bus_dict, ensure_ascii=False)
            bus_data.append(json_bus)

        logger.info("{} bus data retrieved from bus logger fetch".format(counter_result))
        print(' ')

        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False, indent=4).encode('utf-8'), mimetype='application/json; charset=utf-8')



@app.route('/locations/latest') # Retrieve last updated bus for each vehicle number by tsi
def last_updated():
    """
    - Input: None
    - Output: Returns updated bus json (with information, current_location etc.)

    This method returns all last updated bus information about their locations, tsi, route number, last updated timestamp, destination, operator for each bus in whole finland.
    """
    conn = get_connection()
    logger.info("Syncing data for latest to JSON API ...")
    cursor.execute(""" 
        WITH LatestBus AS (
        SELECT bs.*, bus.operator, ROW_NUMBER() OVER (PARTITION BY bs.vehicle_number ORDER BY bs.tsi DESC) AS rn
        FROM bus_status bs
        LEFT JOIN bus ON bus.vehicle_number = bs.vehicle_number
        )
        SELECT * FROM LatestBus WHERE rn = 1
        ORDER BY tsi DESC
        LIMIT 300;
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

        logger.info("{} bus data retrieved from location fetch with the latest data for each bus".format(counter_result))
        print(' ')
        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(bus_data) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False, indent=4).encode('utf-8'), mimetype='application/json; charset=utf-8')



@app.route('/vehicles/<int:vehicle_number>') # By default method = GET to retrieve data, doesen't PUT/POST or change the data
def get_vehicle(vehicle_number: int):
    """
    - Input: vehicle number
    - Returns: Json data about a specific vehicle 

    This method takes in a specific vehicle number and returns all the saved/stored/events information about it. 

    """
    conn = get_connection()
    logger.info("Syncing data for vehicle number {} to JSON API ...".format(vehicle_number))
    cursor.execute("""SELECT bus_status.*, stop.*, bus.operator, stop_event.status, stop_event.arrival_time_to_the_stop
    FROM bus_status 
    INNER JOIN stop ON stop.id = bus_status.id
    LEFT JOIN bus ON bus.vehicle_number = bus_status.vehicle_number
    LEFT JOIN stop_event ON stop_event.id = stop.stop_event 
    WHERE bus_status.vehicle_number=%s""", (vehicle_number,))

    results = cursor.fetchall() # fetching the result from the query
    counter_result = 0
    if len(results) == 0:
        # If the given vehicle number is not found
        return jsonify({"message": "No data or vehicle found with the given vehicle number"})

    else:
        vehicle_list = []
        for result in results:
            counter_result += 1
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

        logger.info("{} data retrieved from fetch for vehicle_number: {}".format(counter_result, vehicle_number))
        print(' ')

        # Combine the list of JSON strings into a single JSON array
        response_json = "[" + ",".join(vehicle_list) + "]"

        # Parse the JSON array into a Python object
        response_data = json.loads(response_json)

        # Return the Python object as a JSON response with UTF-8 encoding
        return Response(json.dumps(response_data, ensure_ascii=False, indent=4).encode('utf-8'), mimetype='application/json; charset=utf-8')


# This method allows ut to define radius and the location passed in to the url, a variation of the buses_within_radius() where it picks address from the url, or api request 
@app.route('/buses_within_radius/<string:street>/<string:city>/<int:radius>')
def buses_within_radius(street, city, radius):
    """ 
    - input: street and city (or region, building number or other attributes) name to get the location of the user, and a radius to show bus near user
    - output: json data about the buses near the user  
    This function takes as input a street and city name to determine the user's location, as well as a radius to display buses located near the user. 
    The output is a JSON object containing data about the buses in the vicinity of the user.

    """
    logger.info("Syncing data location {} {} within raduis {} to JSON API ...".format(city, street, radius))
    # creating a geolocater variable on my app
    api_key = 'b5c600c5d1284ee0b9abc6c69ef95a3b'
    geocoder = OpenCageGeocode(api_key)
    location = f'{street}, {city}' # called it street and city to simplify, but it can be building number, region or other attributes
    response = geocoder.geocode(location)

    if not response: # handles wrong given address/location to geocoder
        return jsonify({"Error message": "Invalid response from the geocoder service. Please check your location input data or try again later."})

    # if the request was successful
    try: 
        if response and len(response):
            try:
                # Parse the response JSON to extract the latitude and longitude
                lat = response[0]['geometry']['lat']
                lon = response[0]['geometry']['lng']
                # Continue with the rest of your program using lat and lon
            except IndexError:
                print("Index out of range error: No data found in the response.")
            except KeyError as e:
                print(f"KeyError: {e}")
            
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
            counter_result = 0
            if len(results) == 0:
                return jsonify({"message": "No bus found"})
            else:
                bus_data = []
                for result in results:
                    counter_result += 1
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

            logger.info("{} bus data retrieved for the address: {} {}, with radius of: {} meter".format(counter_result, street, city, radius))
            print(' ')
            response_json = "[" + ",".join(bus_data) + "]"

            # Parse the JSON array into a Python object
            response_data = json.loads(response_json)

            # Return the Python object as a JSON response with UTF-8 encoding
            return Response(json.dumps(response_data, ensure_ascii=False, indent=4).encode('utf-8'), mimetype='application/json; charset=utf-8')
    except: 
        error_message = {"error": str(e)}
        return jsonify(error_message), 500





# This method is doing nearly the same as the method below buses_within_radius(),
#   the difference is that i would prefer to use a method like this on my frontend to ensure i can pass the location address with json to this method 
@app.route('/buses_near_me', methods=['POST'])
def buses_near_me():
    """
    - input: street and city name to get the location of the user, and a radius to show bus near user
    - output: json data about the buses near the user  
    This function takes as input a street and city name to determine the user's location, as well as a radius to display buses located near the user. 
    The output is a JSON object containing data about the buses in the vicinity of the user.
    """

    get_connection()

    data = request.get_json()
    api_key = 'b5c600c5d1284ee0b9abc6c69ef95a3b'
    geocoder = OpenCageGeocode(api_key)
    location = data['location'] # getting the requested location fron the json data
    city = location['city']
    street = location['street']
    address = f'{city}, {street}' # called it street and city to simplify, but it can be building number, region or other attributes
    response = geocoder.geocode(address)

    # if the request was successful
    if response.ok:
        # Parse the response JSON to extract the latitude and longitude
        data = response.json()[0]
        lat = data['lat']
        lon = data['lon']
        radius = data['radius']

                # Selecting the latest 'tsi' for each vehicle number, within a given radius
        cursor.execute(
            """
            SELECT * FROM bus_status AS bs
            INNER JOIN (
                SELECT vehicle_number, MAX(tsi) AS max_tsi
                FROM bus_status
                GROUP BY vehicle_number
            ) bs_max ON bs.vehicle_number = bs_max.vehicle_number AND bs.tsi = bs_max.max_tsi
            WHERE earth_distance(ll_to_earth(latitude, longitude), ll_to_earth(%s, %s)) <= %s"""
        , (lat, lon, radius))

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
        return Response(json.dumps(response_data, ensure_ascii=False, indent=4).encode('utf-8'), mimetype='application/json; charset=utf-8')



#@retry(wait_fixed=1000, stop_max_attempt_number=5)  # Retry 5 times with a 1-second delay between retries
def make_request(base_url, params):
    response = requests.get(base_url, params=params, timeout=10)
    #response.raise_for_status()  # Raise an exception if the response status code is not 2xx
    return response

def make_request_with_retry(city, street):

    #Example usage of the return values from this method
    """
    data = response.json()[0]
    lat = data['lat']
    lon = data['lon']

    lat = location.latitude
    lon = location.longitude
    """
    # Define the base URL for the Nominatim API
    # creating a geolocater variable on my app
    nominatim_service = Nominatim(user_agent="ahmet2009@live.no", timeout=10)
    geolocator = RateLimiter(nominatim_service.geocode, min_delay_seconds=1.1)
    base_url = 'https://nominatim.openstreetmap.org/search'
    location = geolocator(f"{city}+{street}")

    # Define the query parameters
    params = {
        'q': f"{city},{street}",
        'format': 'jsonv2'
    }
    # Send a GET request to the API
    response = requests.get(base_url, timeout=10, params=params)
    max_retries = 3
    retry_count = 0
    timeout = 10
    while retry_count < max_retries:
        try:
            response = requests.get(base_url, timeout=timeout, params=params)
            return response
        except requests.exceptions.Timeout:
            retry_count += 1
            if retry_count >= max_retries:
                print("Max retries reached, unable to get a response.")
                return None
            else:
                print(f"Retry {retry_count}...")

def free_data():
    try:
        # Get a database connection and cursor
        conn = get_connection()

        # Insert rows into the temporary table
        cursor.execute("""
            INSERT INTO temp_table
            SELECT bs.*, stop.*, bus.operator, stop_event.status, stop_event.arrival_time_to_the_stop
            FROM bus_status AS bs
            LEFT JOIN bus ON bus.vehicle_number = bs.vehicle_number
            LEFT JOIN stop ON stop.id = bs.stop_id
            LEFT JOIN stop_event ON stop_event.id = stop.stop_event
            ORDER BY bs.tsi DESC
            LIMIT 300;
        """)

        # Delete rows that are not within the selected range
        cursor.execute("""
            DELETE FROM bus_status
            WHERE id NOT IN (SELECT id FROM temp_table);
        """)

        cursor.execute("""
            DELETE FROM stop
            WHERE id NOT IN (SELECT id FROM temp_table);
        """)

        cursor.execute("""
            DELETE FROM stop_event 
            WHERE id NOT IN (SELECT id FROM temp_table);
        """)

        cursor.execute("""
            DELETE FROM bus 
            WHERE id NOT IN (SELECT id FROM temp_table);
        """)

        # Commit the transaction
        conn.commit()

    except Exception as e:
        # Handle any exceptions and possibly roll back the transaction on failure
        print(f"Error: {str(e)}")
        conn.rollback()
    finally:
        # Close the cursor and database connection
        cursor.close()


    
# Define a signal handler for SIGINT (Ctrl+C)
def sigint_handler(signal, frame):
    print("Received SIGINT, stopping Flask app... ")
    # Perform any cleanup necessary (e.g. closing DB connections, releasing the threads ..)
    executor_subscriber_class.join()  # Wait for the MQTT subscriber thread to finish
    # Stop the Flask app
    # Making sure to close the cursor 
    if not cursor.closed: 
        cursor.close()
        
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, sigint_handler)

if __name__ == '__main__':
    time.sleep(0.5)
    logger.info("The application server starting...")
    time.sleep(0.5)
    start_threads()
    #logger.info("The application server started")
    logger.warning("Running the application on port 5001")
    logger.info("API URL EXAMPLE: http://localhost:5001/locations")
    logger.info("Visit: https://github.com/ahmetugsuz/Finland_Bus_Routes for more info")
    logger.info("Refresh the JSON REST page's URL to obtain updated data")
    app.run(host='0.0.0.0', port=5001)



