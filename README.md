# Finland Bus Routes

This project provides a service to consume telemetry from the MQTT server mqtt.hsl.fi,
store the telemetry, and make it searchable through an API.
The API is accessible through HTTP and provides information about the location and next stop of buses in Finland.

## Features

- Consume telemetry from mqtt.hsl.fi
- Store the telemetry
- Make the telemetry searchable in a sane way through an API (http/gRPC/SignalR)
- Optional: Host the infrastructure needed to run the service in docker

## Usage 
Once the containers are running, you can access the API by navigating to http://localhost:5000. The following endpoints are available:

- GET http://localhost:5000/buses_within_radius/<string:street>/<string:city>/<int:radius>: Get a list of buses within a given radius of a specified street and city.
- GET http://localhost:5000/locations: Get a list of each bus in Finland. Shows the last updated value for each bus.
- GET http://localhost:5000/locations/next_stop: Get a list of each bus in Finland with their next stop. Shows the last updated value for each bus.
- GET http://localhost:5000/locations/vehicles/<int:vehicle_number>': Get a list of all saved/stored information about a specific bus with given vehicle number.
