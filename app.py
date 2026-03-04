from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import json
import requests
import numpy as np
import webbrowser
import threading
import Simmpy
import sys
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages
file_path = 'DATASHEET.xlsx'
if getattr(sys, 'frozen', False):
    # Running in a bundle
    base_path = sys._MEIPASS
else:
    # Running in a normal Python environment
    base_path = os.path.dirname(__file__)

file_path = os.path.join(base_path, 'DATASHEET.xlsx')
# Load data initially
def load_data():
    try:
        fixed_wing_df = pd.read_excel(file_path, sheet_name='fixed', header=None)
        quadcopter_df = pd.read_excel(file_path, sheet_name='quad', header=None)
        fixed_wing_df.columns = ['Name', 'Cruise speed', 'Max speed', 'Endurance', 'Ceiling', 'MTOM',
                                 'Aspect Ratio', 'Wing Area', 'Cd0', 'Oswald Coefficient']
        quadcopter_df.columns = ['Name', 'Ceiling', 'Max Wind Resistance', 'MTOM', 'Cd0', 'Max speed',
                                 'Top area', 'Side area']
    except FileNotFoundError:
        fixed_wing_df = pd.DataFrame(columns=[
            'Name', 'Cruise speed', 'Max speed', 'Endurance', 'Ceiling', 'MTOM',
            'Aspect Ratio', 'Wing Area', 'Cd0', 'Oswald Coefficient'])
        quadcopter_df = pd.DataFrame(columns=[
            'Name', 'Ceiling', 'Max Wind Resistance', 'MTOM', 'Cd0', 'Max speed',
            'Top area', 'Side area'])
    return fixed_wing_df, quadcopter_df

fixed_wing_df, quadcopter_df = load_data()

def save_data(fixed_wing_df, quadcopter_df):
    try:
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='w') as writer:
            fixed_wing_df.to_excel(writer, sheet_name='fixed', index=False, header=False)
            quadcopter_df.to_excel(writer, sheet_name='quad', index=False, header=False)
    except Exception as e:
        print(f"Failed to save data: {e}")
        flash("An error occurred while saving the data.", "danger")

@app.route('/')
def index():
    try:
        fixed_wing_list = fixed_wing_df['Name'].tolist()
    except KeyError:
        fixed_wing_list = []
        flash("Error: 'Name' column not found in fixed wing data.", "error")
    
    try:
        quadcopter_list = quadcopter_df['Name'].tolist()
    except KeyError:
        quadcopter_list = []
        flash("Error: 'Name' column not found in quadcopter data.", "error")
    
    return render_template('index.html',
                           fixed_wing_list=fixed_wing_list,
                           quadcopter_list=quadcopter_list,
                           errors={})

@app.route('/run_analysis', methods=['POST'])
def run_analysis():
    errors = {}
    
    # Retrieve and validate form data
    aircraft_type = request.form.get('aircraft_type')
    aircraft_name = request.form.get('aircraft_name')
    manual_wind_input = request.form.get('manual_wind_input') == 'on'
    wind_speed = request.form.get('wind_speed') if manual_wind_input else None
    wind_heading = request.form.get('wind_heading') if manual_wind_input else None
    sea_level_temp = request.form.get('sea_level_temp') if manual_wind_input else None
    sea_level_pressure = request.form.get('sea_level_pressure') if manual_wind_input else None
    icao_code = request.form.get('icao_code') if not manual_wind_input else None
    initial_latitude = request.form.get('initial_latitude')
    initial_longitude = request.form.get('initial_longitude')
    initial_altitude = request.form.get('initial_altitude')
    heading = request.form.get('heading')
    speed = request.form.get('speed')
    
    # Validate ICAO code
    if icao_code and len(icao_code) != 4:
        errors['icao_code'] = "ICAO Code must be exactly 4 letters."
    
   
    
    # Validate latitude and longitude
    if initial_latitude:
        try:
            initial_latitude = float(initial_latitude)
            if not (-90 <= initial_latitude <= 90):
                errors['initial_latitude'] = "Latitude must be between -90 and 90 degrees."
        except ValueError:
            errors['initial_latitude'] = "Initial Latitude must be a valid number."
    
    if initial_longitude:
        try:
            initial_longitude = float(initial_longitude)
            if not (-180 <= initial_longitude <= 180):
                errors['initial_longitude'] = "Longitude must be between -180 and 180 degrees."
        except ValueError:
            errors['initial_longitude'] = "Initial Longitude must be a valid number."
    
    # Validate heading
    if heading:
        try:
            heading = float(heading)
            if not (0 <= heading <= 360):
                errors['heading'] = "Heading must be between 0 and 360 degrees."
        except ValueError:
            errors['heading'] = "Heading must be a valid number."
    
    # Validate speed
    if speed:
        try:
            speed = float(speed)
            # Fetch max speed from the dataframe
            if aircraft_type == 'fixed_wing':
                max_speed = fixed_wing_df.query("Name == @aircraft_name")['Max speed'].values
            else:
                max_speed = quadcopter_df.query("Name == @aircraft_name")['Max speed'].values
            
            if max_speed.size > 0 and speed > max_speed[0]:
                errors['speed'] = f"Speed must be less than or equal to the maximum speed of {max_speed[0]}."
        except ValueError:
            errors['speed'] = "Speed must be a valid number."

    # Validate altitude
    if initial_altitude:
        try:
            initial_altitude = float(initial_altitude)
            # Fetch ceiling from the dataframe
            if aircraft_type == 'fixed_wing':
                ceiling = fixed_wing_df.query("Name == @aircraft_name")['Ceiling'].values
            else:
                ceiling = quadcopter_df.query("Name == @aircraft_name")['Ceiling'].values
            
            if ceiling.size > 0 and initial_altitude > ceiling[0] and initial_altitude > 0:
                errors['initial_altitude'] = f"Initial altitude must be less than or equal to the ceiling of {ceiling[0]}."
        except ValueError:
            errors['initial_altitude'] = "Altitude must be a valid number."

    if errors:
        return render_template('index.html', 
                               aircraft_type=aircraft_type, aircraft_name=aircraft_name,
                               icao_code=icao_code, initial_latitude=initial_latitude,
                               initial_longitude=initial_longitude, heading=heading, speed=speed, initial_altitude = initial_altitude,
                               errors=errors, fixed_wing_list=fixed_wing_df['Name'].tolist(),
                               quadcopter_list=quadcopter_df['Name'].tolist())
    
    ### METAR AQUISITION
    if not manual_wind_input:
        try:
            url = f"https://aviationweather.gov/api/data/metar?ids={icao_code}&format=json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            METAR = response.json()  # Now it's a list
            if not METAR:
                print(f"No METAR data found for ICAO '{icao_code}'.")
            else:
                # It's a list, so take the first observation
                obs = METAR[0]
                TSL = obs.get("temp")          # Temperature in °C
                PSL = obs.get("altim")         # Altimeter / pressure in hPa
                windspd = obs.get("wspd")      # Wind speed in kt
                windhdg = obs.get("wdir")      # Wind direction in degrees

                print("METAR data extracted:")
                print(f"Temperature: {TSL} °C")
                print(f"Pressure: {PSL} hPa")
                print(f"Wind Speed: {windspd} kt")
                print(f"Wind Heading: {windhdg}°")

        except requests.exceptions.RequestException as e:
            print(f"Error fetching METAR data: {e}")


    ### SPECIFIC AIRCRAFT DATA RETRIEVAL
    if aircraft_type == 'fixed_wing':
        aircraft_df = fixed_wing_df
    elif aircraft_type == 'quadcopter':
        aircraft_df = quadcopter_df
    else:
        flash("Invalid aircraft type selected.", category='error')
        return redirect(url_for('index'))

    aircraft_data = aircraft_df[aircraft_df['Name'] == aircraft_name]
    if aircraft_data.empty:
        flash("Selected aircraft not found in the database.", category='error')
        return redirect(url_for('index'))

    aircraft_properties = aircraft_data.iloc[0]

    if aircraft_type == 'fixed_wing':
        MTOM = aircraft_properties['MTOM']
        AR = aircraft_properties['Aspect Ratio']
        WA = aircraft_properties['Wing Area']
        Cd0 = aircraft_properties['Cd0']
        oswald = aircraft_properties['Oswald Coefficient']
        ceiling = aircraft_properties['Ceiling']
        simresults = Simmpy.fix(TSL, PSL, initial_latitude, initial_longitude, heading, windspd, windhdg, initial_altitude, MTOM, AR, WA, Cd0, oswald, 0)
        finalv = np.round(simresults[2][0], decimals=3)
        distancetravelled = np.round(simresults[2][10], decimals=3)
    elif aircraft_type == 'quadcopter':
        MTOM = aircraft_properties['MTOM']
        A = aircraft_properties['Top area']
        As = aircraft_properties['Side area']
        Cd0 = aircraft_properties['Cd0']
        ceiling = aircraft_properties['Ceiling']
        simresults = Simmpy.quad(PSL, TSL, heading, initial_latitude, initial_longitude, windhdg, windspd, 0, speed, initial_altitude, MTOM, Cd0, A, As)
        distancetravelled = np.round(simresults[2][5], decimals=3)
        finalv = np.round(simresults[2][7], decimals=3)

    ### Extracting Results for Rendering ###
    final_latitude = simresults[0]
    final_longitude = simresults[1]
    falltime = np.round(simresults[2][1], decimals=3)
    x = np.round(simresults[2][2], decimals=3)
    y = np.round(simresults[2][3], decimals=3)
    z = np.round(simresults[2][4], decimals=3)
    final_kinetic_energy = np.round(0.5 * MTOM * finalv**2, decimals=3)

    dxv = x.tolist()
    dyv = y.tolist()
    dzv = z.tolist()

    return render_template('results.html', finalv=finalv, falltime=falltime,
                           dxv=json.dumps(dxv), dyv=json.dumps(dyv), dzv=json.dumps(dzv),
                           initial_latitude=initial_latitude, initial_longitude=initial_longitude,
                           final_latitude=final_latitude, final_longitude=final_longitude, distancetravelled=distancetravelled, final_kinetic_energy=final_kinetic_energy)

@app.route('/manage_aircraft')
def manage_aircraft():
    # Load data
    fixed_wing_df, quadcopter_df = load_data()
    
    # Convert to lists of dictionaries for rendering
    fixed_wing_list = fixed_wing_df.to_dict(orient='records')
    quadcopter_list = quadcopter_df.to_dict(orient='records')
    
    # Render the template with the updated lists
    return render_template('manage_aircraft.html', 
                           fixed_wing_list=fixed_wing_list, 
                           quadcopter_list=quadcopter_list)


@app.route('/edit_aircraft/<string:aircraft_type>/<string:name>', methods=['GET', 'POST'])
def edit_aircraft(aircraft_type, name):
    if request.method == 'POST':
        if aircraft_type == 'fixed_wing':
            df = fixed_wing_df
        elif aircraft_type == 'quadcopter':
            df = quadcopter_df
        else:
            flash("Invalid aircraft type.", "error")
            return redirect(url_for('index'))

        # Find the index of the aircraft to be edited
        index = df[df['Name'] == name].index
        if index.empty:
            flash("Aircraft not found.", "error")
            return redirect(url_for('manage_aircraft'))
        
        index = index[0]  # Get the index value from the pandas Index object

        # Update fields from form data
        for column in df.columns:
            if column in request.form:
                # Convert values to appropriate type (float) before updating
                try:
                    if column in ['Cruise speed', 'Max speed', 'Endurance', 'Ceiling', 'MTOM', 'Aspect Ratio', 'Wing Area', 'Cd0', 'Oswald Coefficient', 'Max Wind Resistance', 'Top area', 'Side area']:
                        df.at[index, column] = float(request.form[column])
                    else:
                        df.at[index, column] = request.form[column]
                except ValueError:
                    flash(f"Invalid value for {column}. Please enter a valid number.", "error")
                    return redirect(url_for('edit_aircraft', aircraft_type=aircraft_type, name=name))

        # Save the updated data
        save_data(fixed_wing_df, quadcopter_df)

        # Render the template with updated data
        return render_template('manage_aircraft.html', 
                               edit_mode=True, 
                               aircraft_type=aircraft_type, 
                               name=name, 
                               aircraft_data=df.iloc[index].to_dict(),
                               fixed_wing_list=fixed_wing_df.to_dict(orient='records'),
                               quadcopter_list=quadcopter_df.to_dict(orient='records'))

    # Handle GET request to render the form
    if aircraft_type == 'fixed_wing':
        aircraft_data = fixed_wing_df[fixed_wing_df['Name'] == name].iloc[0].to_dict()
    elif aircraft_type == 'quadcopter':
        aircraft_data = quadcopter_df[quadcopter_df['Name'] == name].iloc[0].to_dict()
    else:
        flash("Invalid aircraft type.", "error")
        return redirect(url_for('index'))
    
    return render_template('manage_aircraft.html', 
                           edit_mode=True, 
                           aircraft_type=aircraft_type, 
                           name=name, 
                           aircraft_data=aircraft_data,
                           fixed_wing_list=fixed_wing_df.to_dict(orient='records'),
                           quadcopter_list=quadcopter_df.to_dict(orient='records'))

@app.route('/delete_aircraft/<string:aircraft_type>/<string:name>', methods=['POST'])
def delete_aircraft(aircraft_type, name):
    # Load data from your data source
    fixed_wing_df, quadcopter_df = load_data()
    
    # Convert dataframes to lists of dictionaries
    fixed_wing_list = fixed_wing_df.to_dict(orient='records')
    quadcopter_list = quadcopter_df.to_dict(orient='records')
    
    # Remove the aircraft from the appropriate list
    if aircraft_type == 'fixed_wing':
        fixed_wing_list = [a for a in fixed_wing_list if a['Name'] != name]
        # Update the dataframe with the new list
        fixed_wing_df = pd.DataFrame(fixed_wing_list)
    elif aircraft_type == 'quadcopter':
        quadcopter_list = [a for a in quadcopter_list if a['Name'] != name]
        # Update the dataframe with the new list
        quadcopter_df = pd.DataFrame(quadcopter_list)
    
    # Save the updated data back to the data source
    save_data(fixed_wing_df, quadcopter_df)
    
    # Provide feedback and redirect
    flash(f'{aircraft_type.capitalize()} deleted successfully!', 'success')
    return redirect(url_for('manage_aircraft'))



@app.route('/add_aircraft', methods=['POST'])
def add_aircraft():
    aircraft_type = request.form['aircraft_type']
    
    # Initialize aircraft data dictionary
    aircraft_data = {
        'fixed_wing' : {
        'Name': request.form.get('Name'),
        'Cruise Speed': request.form.get('Cruise Speed'),
        'Max Speed': request.form.get('Max Speed'),
        'Endurance': request.form.get('Endurance'),
        'Ceiling': request.form.get('Ceiling'),
        'MTOM': request.form.get('MTOM'),
        'Aspect Ratio': request.form.get('Aspect Ratio'),
        'Wing Area': request.form.get('Wing Area'),
        'Cd0': request.form.get('Cd0'),
        'Oswald Coefficient': request.form.get('Oswald Coefficient')
    },
        'quadcopter' : {
        'Name': request.form.get('Name'),
        'Max Speed': request.form.get('Max Speed'),
        'Endurance': request.form.get('Endurance'),
        'Ceiling': request.form.get('Ceiling'),
        'MTOM': request.form.get('MTOM'),
        'Cd0': request.form.get('Cd0'),
        'Max Wind Resistance': request.form.get('Max Wind Resistance'),
        'Side Area': request.form.get('Side Area'),
        'Top Area': request.form.get('Top Area')
    }
    
    
    
    
    
    }
    
    # Remove None values from aircraft_data
    aircraft_data = [v for k, v in aircraft_data[aircraft_type].items() if v is not None]
    
    if aircraft_type == 'fixed_wing':
        print("DATA FIXED LOADED", fixed_wing_df)
        fixed_wing_df.loc[len(fixed_wing_df)] = aircraft_data
        
    elif aircraft_type == 'quadcopter':
        print("DATA QUAD LOADED", aircraft_data)
        quadcopter_df.loc[len(quadcopter_df)] = aircraft_data
    else:
        flash("Invalid aircraft type.", "error")
        return redirect(url_for('manage_aircraft'))

    save_data(fixed_wing_df, quadcopter_df)
    flash(f'{aircraft_type} added successfully!', 'success')
    return redirect(url_for('manage_aircraft'))
if __name__ == '__main__':
    # Function to open the browser
    def open_browser():
        webbrowser.open("http://127.0.0.1:5000/")

    # Start the Flask app in a separate thread
    threading.Thread(target=open_browser).start()
    
    # Run the Flask app
    if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))