import pandas as pd
import random
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import requests
from datetime import datetime, timezone
from pprint import pprint 

dash.register_page(__name__, path='/flight-status')

layout = html.Div([
        html.H1("Flight status", style={'font-family': 'Verdana', 'color': '#000080', 'margin-left': '5px', 'font-size': '25px'}),
        html.Label('Select origin airport:'),
        dcc.Dropdown(id='flight-dropdown', options=[],  value=''),
        dcc.Graph(id= 'flight-status-graph', style = {"height":"80vh"}),
        html.Div(id = 'status-toast-placeholder')
    ]) 
    
@callback(Output('flight-dropdown', 'options'),
           Input('flights-data', 'data'))
def fill_flight_dropdown(flights): 
    df = pd.DataFrame(flights)
    flight_options = [f"{row['airline']}{row['flight_number']}" for index, row in df.iterrows()]
    return flight_options

@callback([Output('flight-status-graph', 'figure'),
    Output('status-toast-placeholder', 'children')],
    Input('flight-dropdown', 'value'),
    State('airports-data', 'data'))
    
def update_map(flightNumber, airports): 
    # If no airports are selected, display the initial map
    if not flightNumber: return dash.no_update, []
        
    # ~ df = pd.DataFrame(airports)
    # If both airports are selected, filter the data to include only the selected airports
    # ~ selected_airports = df.loc[df['codeIATA'].isin([origin_code, dest_code])]
    airports = pd.DataFrame(airports)
    response = requests.get(f"http://fastapi:8000/flight_status/{flightNumber}", auth=('sabrine', 'sab_project23'))
    r = response.json()['FlightStatusResource']['Flights']['Flight'][0]
    status = r["FlightStatus"]["Code"]
    if status == 'DP': arr_key, dep_key = 'Estimated', 'Actual'
    elif status == 'LD': arr_key, dep_key = 'Actual', 'Actual' 
    else:
        return go.Figure(), dbc.Toast('Flight status is unknown',
                            header="Flight Information",
                            dismissable=True,
                            is_open=True,
                            style={"position": "fixed", "top": 100, "right": 10}) 
    arr_key_api = arr_key + 'TimeLocal' 
    dep_key_api = dep_key +'TimeLocal'
    toast =  html.Div([
        dbc.Toast(
            dbc.ListGroup([
                dbc.ListGroupItem(f'Flight Status : {r["FlightStatus"]["Definition"]}'),
                dbc.ListGroupItem(f'Time Status : {r["Arrival"]["TimeStatus"]["Definition"]}'),
                dbc.ListGroupItem(f'Scheduled Departure : {r["Departure"]["ScheduledTimeLocal"]["DateTime"].replace("T", " ")}'),
                dbc.ListGroupItem(f'{dep_key} Departure : {r["Departure"][dep_key_api]["DateTime"].replace("T", " ")}'),
                dbc.ListGroupItem(f'Scheduled Arrival : {r["Arrival"]["ScheduledTimeLocal"]["DateTime"].replace("T", " ")}'),
                dbc.ListGroupItem(f'{arr_key} Arrival : {r["Arrival"][arr_key_api]["DateTime"].replace("T", " ")}'),
                ]),
            header="Flight Information",
            dismissable=True,
            is_open=True
            )],
        style={"position": "fixed", "top": 100, "right": 10})
    origin = airports[airports['codeIATA'] == r['Departure']['AirportCode']]
    dest = airports[airports['codeIATA'] == r['Arrival']['AirportCode']]
    arrival = datetime.strptime(r['Arrival'][arr_key + 'TimeUTC']['DateTime'], '%Y-%m-%dT%H:%MZ')
    departure = datetime.strptime(r['Departure'][dep_key +'TimeUTC']['DateTime'], '%Y-%m-%dT%H:%MZ')
    now = datetime.now()
    lon_origin , lat_origin = origin['lon'].iloc[0],  origin['lat'].iloc[0]
    lon_dest , lat_dest = dest['lon'].iloc[0],  dest['lat'].iloc[0]
    if departure > now:
        lon = lon_origin
        lat = lat_origin
    elif arrival < now:
        lon = lon_dest
        lat = lat_dest
    else:
        flight_time = arrival - departure
        remaining_time = arrival - now
        done_ratio = 1 - (remaining_time / flight_time)
        lon = (lon_dest - lon_origin) * done_ratio + lon_origin
        lat = (lat_dest - lat_origin) * done_ratio + lat_origin
    
    fig = go.Figure(go.Scattermapbox(
            mode = "markers+lines",
            lon = [lon_origin, lon, lon_dest],
            lat = [lat_origin, lat, lat_dest],
            marker = {'size': 15}))
            
    fig.add_trace(go.Scattermapbox(
            mode = "markers",
            lon = [lon],
            lat = [lat],
            marker = {'size': 7}))
             
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}) 
        
    return fig, toast
