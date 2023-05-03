import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, callback
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import requests
from pprint import pprint

dash.register_page(__name__, path='/')

def layout():
    return html.Div([ 
    dcc.Graph(id = 'airport-graph', style = {"height":"80vh"}),
    html.Div(id = 'data-info')
    ])
     
@callback(Output('airport-graph', 'figure'),
            Input('airports-data', 'data'))
def display_airports(airports):
    if not airports: return dash.no_update 
    fig = px.scatter_mapbox(airports, lat="lat", lon="lon", hover_name="airport_name", hover_data=["codeIATA", "city"], zoom = 3,
    mapbox_style = 'open-street-map') 
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})  
    return fig
    
@callback(Output('data-info', 'children'),
              Input('airport-graph', 'clickData'))
def select_data(data):
    # Prevent update if no selected data
    if not data: return dash.no_update
    IATA = data['points'][0]['customdata'][0]
    departures_flight = requests.get(f'http://fastapi:8000/departures/{IATA}', auth=('sabrine', 'sab_project23')) 
    arrivals_flight = requests.get(f'http://fastapi:8000/arrivals/{IATA}', auth=('sabrine', 'sab_project23'))
    return html.Div([
        dbc.Toast(
            dbc.ListGroup(
            [dbc.ListGroupItem(f'{i["airline"]}{i["flight_number"]} To: {i["ArrivalAirport"]} Departure: {i["STD"].replace("T", " ")}') for i in departures_flight.json()]
            ),
            header="Departures",
            dismissable=True,
            is_open=True
            ),
        dbc.Toast(
            dbc.ListGroup(
            [dbc.ListGroupItem(f'{i["airline"]}{i["flight_number"]} From: {i["DepartAirport"]} Arrival: {i["ATD"].replace("T", " ")}') for i in arrivals_flight.json()]
            ),
            header="Arrivals",
            dismissable=True,
            is_open=True
            )
        ],
        style={"position": "fixed", "top": 108, "right": 10})
