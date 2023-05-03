import dash
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import requests
import pandas as pd

app = Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

app.layout = html.Div([
    html.Div([
        html.Img(src='https://www.dewebsite.org/logo/lufthansa/lufthansa_bot.jpg', style={'width': '70px', 'height': '70px'}),
        html.H1('Lufthansa Track', style={'font-family': 'Verdana', 'color': '#000080', 'margin-left': '10px'})
    ], style={'display': 'flex', 'align-items': 'center'}),
    html.Div([
        dbc.Button("Home", href="/", style={'margin-right': '10px'}),
        dbc.Button("Flight by route", href="/flight-route", style={'margin-right': '10px'}),
        dbc.Button("Flight status", href="/flight-status", style={'margin-right': '10px'})
    ], 
    style = {'margin-left':'10px'}),
    dash.page_container,
    dcc.Interval(id = 'data-refresh', interval =60*1000, n_intervals=0),
    dcc.Store(id = 'airports-data', storage_type='session'),
    dcc.Store(id = 'flights-data', storage_type='session'),
    ])

@app.callback(Output('airports-data', 'data'),
            Input('data-refresh', 'n_intervals'))
def refresh_airports(n): 
    response_airports = requests.get('http://fastapi:8000/airports', auth=('sabrine', 'sab_project23'))
    data = response_airports.json()
    # Flatten the list of lists
    flat_data = [item for sublist in data['airports'] for item in sublist]
    airports = pd.DataFrame(flat_data, columns=["country", "airport_name", "city", "lon", "codeIATA", "lat"])
    airports = airports.dropna()
    return airports.to_dict() 
    
@app.callback(Output('flights-data', 'data'),
            Input('data-refresh', 'n_intervals'))
def refresh_flights(n): 
    response_flights = requests.get('http://fastapi:8000/flights/today', auth=('sabrine', 'sab_project23'))
    flights = pd.DataFrame(response_flights.json())
    return flights.to_dict()

if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=5000)
