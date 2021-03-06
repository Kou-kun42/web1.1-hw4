import jinja2
import matplotlib
import matplotlib.pyplot as plt
import os
import pytz
import requests
import sqlite3
import time

from pprint import PrettyPrinter
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file
from geopy.geocoders import Nominatim
from io import BytesIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas


################################################################################
## SETUP
################################################################################

app = Flask(__name__)

# Get the API key from the '.env' file
load_dotenv()
API_KEY = os.getenv('API_KEY')


# Settings for image endpoint
# Written with help from http://dataviztalk.blogspot.com/2016/01/serving-matplotlib-plot-that-follows.html
matplotlib.use('agg')
plt.style.use('ggplot')

my_loader = jinja2.ChoiceLoader([
    app.jinja_loader,
    jinja2.FileSystemLoader('data'),
])
app.jinja_loader = my_loader

pp = PrettyPrinter(indent=4)


################################################################################
## ROUTES
################################################################################

@app.route('/')
def home():
    """Displays the homepage with forms for current or historical data."""
    context = {
        'min_date': (datetime.now() - timedelta(days=5)),
        'max_date': datetime.now(),
        'future_start': (datetime.now() + timedelta(days=1)),
        'future_end': (datetime.now() + timedelta(days=4))
    }
    return render_template('home.html', **context)

def get_letter_for_units(units):
    """Returns a shorthand letter for the given units."""
    return 'F' if units == 'imperial' else 'C' if units == 'metric' else 'K'

@app.route('/results')
def results():
    """Displays results for current weather conditions."""
    # TODO: Use 'request.args' to retrieve the city & units from the query
    # parameters.
    city = request.args.get("city")
    units = request.args.get("units")

    url = 'http://api.openweathermap.org/data/2.5/weather'
    params = {
        "appid": API_KEY,
        "q": city,
        "units": units
    }

    result_json = requests.get(url, params=params).json()

    # Uncomment the line below to see the results of the API call!
    # pp.pprint(result_json)

    # TODO: Replace the empty variables below with their appropriate values.
    # You'll need to retrieve these from the result_json object above.

    # For the sunrise & sunset variables, I would recommend to turn them into
    # datetime objects. You can do so using the `datetime.fromtimestamp()` 
    # function.
    context = {
        'date': datetime.now(),
        'city': result_json["name"],
        'description': result_json["weather"][0]["description"],
        'temp': result_json["main"]["temp"],
        'humidity': result_json["main"]["humidity"],
        'wind_speed': result_json["wind"]["speed"],
        'sunrise': time.strftime('%H:%M:%S', time.localtime(result_json["sys"]["sunrise"])),
        'sunset': time.strftime('%H:%M:%S', time.localtime(result_json["sys"]["sunset"])),
        'units_letter': get_letter_for_units(units)
    }

    return render_template('results.html', **context)

def get_min_temp(results):
    """Returns the minimum temp for the given hourly weather objects."""
    min_temp = results[0]["temp"]
    for obj in results:
        if obj["temp"] < min_temp:
            min_temp = obj["temp"]
    return min_temp

def get_max_temp(results):
    """Returns the maximum temp for the given hourly weather objects."""
    max_temp = results[0]["temp"]
    for obj in results:
        if obj["temp"] > max_temp:
            max_temp = obj["temp"]
    return max_temp

def get_lat_lon(city_name):
    geolocator = Nominatim(user_agent='Weather Application')
    location = geolocator.geocode(city_name)
    if location is not None:
        return location.latitude, location.longitude
    return 0, 0


@app.route('/historical_results')
def historical_results():
    """Displays historical weather forecast for a given day."""
    city = request.args.get("city")
    date = request.args.get("date")
    print(date)
    units = request.args.get("units")
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    date_in_seconds = date_obj.strftime('%s')

    latitude, longitude = get_lat_lon(city)

    url = 'http://api.openweathermap.org/data/2.5/onecall/timemachine'
    params = {
        # TODO: Enter query parameters here for the 'appid' (your api key),
        # latitude, longitude, units, & date (in seconds).
        # See the documentation here (scroll down to "Historical weather data"):
        # https://openweathermap.org/api/one-call-api
        "appid": API_KEY,
        "lat": latitude,
        "lon": longitude,
        "units": units,
        "dt": date_in_seconds
    }

    result_json = requests.get(url, params=params).json()

    # Uncomment the line below to see the results of the API call!
    # pp.pprint(result_json)

    result_current = result_json['current']
    result_hourly = result_json['hourly']

    # TODO: Replace the empty variables below with their appropriate values.
    # You'll need to retrieve these from the 'result_current' object above.
    context = {
        'city': city,
        'date': date_obj,
        'lat': latitude,
        'lon': longitude,
        'units': units,
        'units_letter': get_letter_for_units(units), # should be 'C', 'F', or 'K'
        'description': result_current["weather"][0]["description"],
        'temp': result_current["temp"],
        'min_temp': get_min_temp(result_hourly),
        'max_temp': get_max_temp(result_hourly)
    }

    return render_template('historical_results.html', **context)

# Gets the average temp for a day
def get_avg_temp(results):
    temps = []
    for obj in results:
        temps.append(obj["main"]["temp"])
    return sum(temps) / len(temps)

# Gets the average temp for a day
def get_min_ftemp(results):
    min_temp = results[0]["main"]["temp_min"]
    for obj in results:
        if obj["main"]["temp_min"] < min_temp:
            min_temp = obj["main"]["temp_min"]
    return min_temp

# Gets the average temp for a day
def get_max_ftemp(results):
    max_temp = results[0]["main"]["temp_max"]
    for obj in results:
        if obj["main"]["temp_max"] > max_temp:
            max_temp = obj["main"]["temp_max"]
    return max_temp

# I tried to do the 4 day forecast but it seems we need a paid account api key.
# This is the code that I think should work but I have no way of testing it.
@app.route("/forecast_results")
def forecast_results():
    """Displays future weather forecast for a given day."""

    city = request.args.get("city")
    date = request.args.get("date")
    units = request.args.get("units")
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    dt = date_obj.strftime('%s')

    latitude, longitude = get_lat_lon(city)

    url = 'http://api.openweathermap.org/data/2.5/forecast/hourly'
    params = {
        "appid": API_KEY,
        "lat": latitude,
        "lon": longitude,
        "units": units,
    }

    result_json = requests.get(url, params=params).json()
    
    pp.pprint(result_json)

    # Find the right day from the results
    day_list = []
    for day in result_json["list"]:
        if date in day["dt_txt"]:
            day_list.append(day)

    context = {
        'city': city,
        'date': date_obj,
        'lat': latitude,
        'lon': longitude,
        'units': units,
        'units_letter': get_letter_for_units(units), # should be 'C', 'F', or 'K'
        'description': day_list[0]["weather"][0]["description"],
        'temp': get_avg_temp(day_list),
        'min_temp': get_min_ftemp(day_list),
        'max_temp': get_max_ftemp(day_list)
    }

    return render_template('forecast_results.html', **context)

################################################################################
## IMAGES
################################################################################

def create_image_file(xAxisData, yAxisData, xLabel, yLabel):
    """
    Creates and returns a line graph with the given data.
    Written with help from http://dataviztalk.blogspot.com/2016/01/serving-matplotlib-plot-that-follows.html
    """
    fig, _ = plt.subplots()
    plt.plot(xAxisData, yAxisData)
    plt.xlabel(xLabel)
    plt.ylabel(yLabel)
    canvas = FigureCanvas(fig)
    img = BytesIO()
    fig.savefig(img)
    img.seek(0)
    return send_file(img, mimetype='image/png')

@app.route('/graph/<lat>/<lon>/<units>/<date>')
def graph(lat, lon, units, date):
    """
    Returns a line graph with data for the given location & date.
    @param lat The latitude.
    @param lon The longitude.
    @param units The units (imperial, metric, or kelvin)
    @param date The date, in the format %Y-%m-%d.
    """
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    date_in_seconds = date_obj.strftime('%s')


    url = 'http://api.openweathermap.org/data/2.5/onecall/timemachine'
    params = {
        'appid': API_KEY,
        'lat': lat,
        'lon': lon,
        'units': units,
        'dt': date_in_seconds
    }
    result_json = requests.get(url, params=params).json()

    hour_results = result_json['hourly']

    hours = range(24)
    temps = [r['temp'] for r in hour_results]
    image = create_image_file(
        hours,
        temps,
        'Hour',
        f'Temperature ({get_letter_for_units(units)})'
    )
    return image


if __name__ == '__main__':
    app.run(debug=True)
