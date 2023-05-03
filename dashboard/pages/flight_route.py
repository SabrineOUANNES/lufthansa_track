import pandas as pd
import random
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import requests
import datetime
from datetime import datetime 

dash.register_page(__name__, path='/flight-route')

def layout(): 
    # Generate the dropdown options
    return html.Div([
        html.H1("Flight by route", style={'font-family': 'Verdana', 'color': '#000080', 'margin-left': '5px', 'font-size': '25px'}),
        html.Label('Select origin airport:'),
        dcc.Dropdown(id='origin-dropdown', options=[], value=''),
        html.Label('Select destination airport:'),
        dcc.Dropdown(id='destination-dropdown', options=[], value=''),
        html.Button('Search', id='search-button', n_clicks=0, style={'background-color': 'skyblue', 'font-size': '20px'}), 
        dcc.Graph(id= 'flight-route-graph', style = {"height":"80vh"}), 
        dcc.Markdown("No flights found between the selected airports.", id='route-error-message', style={'color': 'red', 'display': 'none'}),
        html.Div(id = 'route-toast-placeholder')
    ])
    
@callback([Output('origin-dropdown', 'options'),
           Output('destination-dropdown', 'options')],
           Input('airports-data', 'data'))
def fill_aiport_dropdowns(airports): 
    df = pd.DataFrame(airports)
    airport_options = [{'label': f"({row['codeIATA']}) {row['airport_name']}", 'value': row['codeIATA']} for index, row in df.iterrows()]
    return airport_options, airport_options
    
@callback(
    [Output('flight-route-graph', 'figure'),
    Output('route-toast-placeholder', 'children'),
    Output('route-error-message', 'style')],
    [Input('search-button', 'n_clicks')],
    [State('origin-dropdown', 'value'),
     State('destination-dropdown', 'value'),
     State('airports-data', 'data')])
def update_map(n_clicks, origin_code, dest_code, airports): 
    # If no airports are selected, display the initial map
    if not (origin_code and dest_code and n_clicks):
        return dash.no_update ,[], {'color': 'red', 'display': 'none'}
    if (origin_code and dest_code and n_clicks > 0):
        df = pd.DataFrame(airports)
        # If both airports are selected, filter the data to include only the selected airports
        selected_airports = df.loc[df['codeIATA'].isin([origin_code, dest_code])]
        print(selected_airports) 
        fig = go.Figure(go.Scattermapbox(
            lat = selected_airports['lat'].to_list(),
            lon = selected_airports['lon'].to_list(),
            mode = 'markers+lines',
            marker=go.scattermapbox.Marker(size=9),
            text = selected_airports['airport_name'].to_list(),
            ))
            
        # ~ fig = px.line_mapbox(selected_airports, lat="lat", lon="lon",
                # ~ hover_name="airport_name", hover_data=["codeIATA", "city"], zoom=3)
        fig.update_layout(mapbox_style="open-street-map")
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        
        response = requests.get(f"http://fastapi:8000/flights_by_route?origin={origin_code}&destination={dest_code}", auth=('sabrine', 'sab_project23'))
        toast =  html.Div([
        dbc.Toast(
            dbc.ListGroup(
                [dbc.ListGroupItem(f'{i[0]["airline"]}{i[0]["flight_number"]} Departure: {i[0]["STD"].replace("T", " ")}') for i in response.json()['flights']]
                ),
            header="Next flights",
            dismissable=True,
            is_open=True
            )],
        style={"position": "fixed", "top": 140, "right": 10})
        
        return fig, toast, {'color': 'red', 'display': 'none'}
    return dash.no_update, [], {'color': 'red', 'display': 'block'}
