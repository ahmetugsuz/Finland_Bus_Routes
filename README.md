# Finland Bus Routes

Welcome to the Finland Bus Routes project! This application provides a service to consume telemetry from the MQTT broker server mqtt.hsl.fi, store the telemetry, and make it searchable through an API. The API is accessible through HTTP and provides information about the location, next stop of the buses in Finland and more via this application.


## Table Of Contents



## Features
This project includes the following features:
- Consume telemetry from mqtt.hsl.fi
- Store the telemetry
- Make the telemetry searchable in a sane way through an API (http/gRPC/SignalR)
- Host the infrastructure needed to run the service in docker


## Overview

**Finland Bus Routes** is a comprehensive service designed to capture real-time telemetry data from the MQTT server, mqtt.hsl.fi. This service not only gathers telemetry data but also stores it for future use, making it easily accessible via a user-friendly API. Its primary focus is to provide up-to-date information about bus locations, upcoming stops, and more, specifically for the bus network in Finland. It also includes a cleanup program that manages database memory. This feature can be particularly useful when the intended use of this program is for a short or long duration, allowing you to set up a time management schedule for cleaning up the database.    

**Purpose:** This project was created to help commuters, travelers, and developers access up-to-date information about bus routes and schedules in Finland. My goal is to provide an easy-to-use and reliable source of data for a better public transportation experience. If desired, I also aim to develop a frontend for this backend service, creating a full-stack application that can be widely utilized.  

**Key Benefits:** With Finland Bus Routes, users can quickly find information about buses near their location, search for buses based on specific locations in Finland using their city and street names within a specified radius, check the every record stored of a bus by their vehicle number, retrieve current location, route number, destination, operator, status, arrival time to the next stop, and more for every bus that is currently in active status in Finland.  

**Audience:** This project is designed for public transportation enthusiasts, developers, and anyone looking to streamline their bus travel experience in Finland.  

**License:** This project is open-source and available under the MIT License.  

**Contributing:** If you'd like to get involved, please refer to my website and contact me: ahmettu.com.  

**Status:** Finland Bus Routes is actively maintained and continuously updated to provide the latest and most accurate bus telemetry data.  

## Getting Started


To run the application, you can use Docker Compose, which simplifies the setup process. Here's how to do it:

### Method 1: Using Docker Compose (Recommended, Easiest Way)

#### Building the Application

1. Clone the GitHub repository to your local machine:
    - `git clone https://github.com/ahmetugsuz/Finland_Bus_Routes`  

2. Change (if you're not in this directory already) to the project's directory:  
    - `cd Finland_Bus_Routes`   

3. Make sure the `docker-compose.yml` file is present in the project's root directory, and
    that you have Docker Desktop installed on your machine.

#### Running the Application

4. Running the application
    - `docker-compose build`  

5. Run the following command to start the application using Docker Compose:
    - `docker-compose up`  

6. Access the API at http://localhost:5001/{API-endpoint} and interact with it as described in the Usage section.  

7. To stop the application, press:
    - `Ctrl+C` in the terminal  
    or 
    run the following command:   
    - `docker-compose down` in a separate terminal window.

Running docker-compose down will not only stop the application but also remove the associated Docker images. If you wish to restart the application, you'll need to rebuild it with the following instructions in part 4.  

These steps allow you to easily start and stop the entire application, including all the required services, using Docker Compose.


### Method 2: Running Docker commands manually
1. Pull the database image:
    - `docker pull ahmettugsuz/all_bus_routes_finland:db-v1.0`   
2. Run the database container:
    - `docker run -d --name bus_routes_db -p 5432:5432 -e POSTGRES_USER=ahmettugsuz -e POSTGRES_PASSWORD=bus_finland -e POSTGRES_DB=bus_data ahmettugsuz/all_bus_routes_finland:db-v1.0`    
3. Pull the application image:
    - `docker pull ahmettugsuz/all_bus_routes_finland:app-v1.0` 
4. Run the application container:
    - `docker run -d --name bus_routes_container -p 5001:5001 --link bus_routes_db:host-bus_routes_db ahmettugsuz/all_bus_routes_finland:app-v1.0` 
5. Access the API at http://localhost:5001 and interact with it as described in the Usage section.  

6. To stop the application, run the following commands:  
    - `docker stop bus_routes_container`
    - `docker stop bus_routes_db`
7. To remove the images:
    - `docker rm bus_routes_container`   
    - `docker rm bus_routes_db`  


## Usage 


Once the containers are up and running, you can access the API endpoints by navigating to http://localhost:5001 and appending the desired endpoint to the URL. Alternatively, click on the endpoints listed below.
The following endpoints are available:   

- **[GET] http://localhost:5001/locations**  

This endpoint returns JSON data of locations for active buses in Finland, displaying the most recent updates for each bus.   

**JSON format:** The JSON objects will be structured the same as the example objects format provided for the example response for /buses_within_radius API-endpoint as shown down below.  

- **[GET] http://localhost:5001/locations/next_stop**  

This endpoint returns JSON data of locations and their next stop information for active buses in Finland, displaying the most recent updates for each bus.  

**JSON format:** The JSON objects will be structured the same as the example objects format provided for the example response for /vehicle_number API-endpoint as shown down below.  

- **[GET] http://localhost:5001/locations/logger**   

This historical endpoint provides a log of all related data for each active bus in Finland. It allows you to access a comprehensive record of information about each bus, including historical data and changes over time.

**JSON format:** The JSON objects will be structured the same as the example objects format provided for the example response for /buses_within_radius API-endpoint as shown down below.  

- **[GET] http://localhost:5001/locations/latest**  

This endpoint accumulates and provides the most recently available recorded data for each active bus in Finland. It offers data collected up to the last telemetry signal received for each bus, which may vary based on their individual transmission frequencies.

**JSON format:** The JSON objects will be structured the same as the example objects format provided for the example response for /buses_within_radius API-endpoint as shown down below.  

- **[GET] http://localhost:5001/vehicles/{vehicle_number}**   

    This endpoint allows users to retrieve specific information for a vehicle by providing its unique vehicle number as a parameter in the URL.  

    **Parameters:**   
    vehicle_number (integer): The unique identifier for the vehicle. Replace {vehicle_number} in the URL with the actual vehicle number.  

    **Example:**  
    To retrieve information for a vehicle with the number 1340, make a GET request to:  
    - http://localhost:5001/vehicles/1340  

    **Example response for vehicle number 1340:**  
    ```json
    [
        {
            "vehicle_number": 1340,
            "route_number": "731N",
            "utc_timestamp": "21:30:07",
            "current_location": "Lahdenväylä, Viikinranta, Uusimaa",
            "destination": "Kulomäki",
            "next_stop": "Kamppi",
            "operator": "Helsingin Bussiliikenne Oy",
            "status": "Driving",
            "arrival_time_to_the_stop": "None"
        },
        {
            "vehicle_number": 1340,
            "route_number": "731N",
            "utc_timestamp": "21:45:28",
            "current_location": "Lahdenväylä, Kolohonka, Uusimaa",
            "destination": "Kulomäki",
            "next_stop": "Lugnet",
            "operator": "Helsingin Bussiliikenne Oy",
            "status": null,
            "arrival_time_to_the_stop": "None"
        }, 
    ]
    ```  


- **[GET] http://localhost:5001/buses_within_radius/{street}/{city}/{radius}**  

    This endpoint allows users to search for buses within a specified radius based on various attributes such as street, city, region, or building number. Users can provide any combination of two of these attributes. The outcome depends on the specified radius; a larger radius captures signals from buses within a broader area around the address given in the url.

    **Parameters:**  
    -  building number (int): The number of the building (optional).  
    -  street (string): The name of the street or specific location (optional).  
    -  city (string): The city in Finland (optional).  
    -  region (string): The region within Finland (optional).  
    -  radius (integer): The search radius in meters.  

    **Example:**    
    To find buses within a 500-meter radius of Mannerheimintie in Uusimaa, make a GET request to:  
    - http://localhost:5001/buses_within_radius/Mannerheimintie/Uusimaa/500  

    **Example Requests:**    
    i. Search by street and city, within a radius of 1000 meters:    
       - Request example: /buses_within_radius/Mannerheimintie/Helsinki/1000  

    ii. Search by street and region only, within a radius of 2000 meters:  
       - Request example: /buses_within_radius/Mannerheimintie/Helsinki/2000

    iii. Search by street and building number, within a radius of 500 meters:  
       - Request example: /buses_within_radius/22/Tullivuorentie/500    

    And more of these type of combinations ...  


    ***Example Response on http://localhost:5001/buses_within_radius/Mannerheimintie/Uusimaa/500:***
    ```json
    [
        {
            "vehicle_number": 1932,
            "route_number": "108N",
            "utc_timestamp": "21:27:54",
            "current_location": "3a, Topeliuksenkatu, Uusimaa",
            "destination": "Kamppi",
            "operator": "Helsingin Bussiliikenne Oy",
            "next_stop": "Töölöntori"
        },
        {
            "vehicle_number": 446,
            "route_number": "231N",
            "utc_timestamp": "21:28:27",
            "current_location": "88, Mannerheimintie, Uusimaa",
            "destination": "Elielinaukio",
            "operator": "Oy Pohjolan Liikenne Ab",
            "next_stop": "Töölön kisahalli"
        },
        {
            "vehicle_number": 1247,
            "route_number": "40",
            "utc_timestamp": "21:28:30",
            "current_location": "50, Mannerheimintie, Uusimaa",
            "destination": "Elielinaukio",
            "operator": "Nobina Finland Oy",
            "next_stop": "Hesperian puisto"
        },
    ]
    ```

    ***Note:*** Replace the `street`, `city`, and `radius` values in the URL with your desired location and radius parameters.  

    ***Remember:***  A higher radius targets larger area around the address provided in the url.  

- **[POST] /buses_near_me**  

    This endpoint is designed for frontend use and allows users to request bus information near a specified location.
    It operates as a POST method to enable the frontend to send location data to the backend and receive bus data in response.

    **Input Parameters:**  

    - `location:` A JSON object containing information about the user's location, including street and city names (e.g., "street": "Turunväylä", "city": "Vehkamäki"). 
    - `radius:` The radius (in meters) within which to search for buses near the provided location.  

    **Example Request (request body):**
    ```json
    POST /buses_near_me
    {
        "location": {
        "street": "Turunväylä",
        "city": "Vehkamäki"
        },
        "radius": 150
    }
    ```  

    **Example response from the backend to the frontend on request:**  
    ```json
    [
        {
            "vehicle_number": 1053,
            "route_number": "520",
            "utc_timestamp": "22:06:50",
            "current_location": "Turunväylä, Vehkamäki, Uusimaa",
            "destination": "Matinkylä (M)",
            "operator": "Oy Pohjolan Liikenne Ab",
            "next_stop": "Nihtisilta"
        }
    ]
    ```

## More Information