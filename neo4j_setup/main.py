from datetime import datetime, timedelta
import requests
from neo4j import GraphDatabase
import pandas as pd
import csv
import io
import configparser

config = configparser.ConfigParser()
config.read('config.ini')
client_id = config.get('credentials', 'client_id')
client_secret = config.get('credentials', 'client_secret')
credentials = {'client_id':client_id, 'client_secret':client_secret,'grant_type':'client_credentials'}

##      Airport Request
response = requests.get("https://query.data.world/s/iizp6mghtd73iij65xv5imaavvhr6p?dws=00000")
airports = []
# Parse response content as CSV
csv_reader = csv.DictReader(io.StringIO(response.content.decode('utf-8')))
# Convert CSV rows to a list of airport dictionaries
for row in csv_reader:
        airport = {
                'airport_name': row['Airport Name'],
                'codeIATA': row['three-digit code'],
                'country': row['Country'],
                'city': row['City'],
                'lat': float(row['l1']),
                'lon': float(row['l2'])
        }
        airports.append(airport)
        
airports = pd.DataFrame(airports)
airports = airports[airports['codeIATA'] != '']

driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'neo4jproject'))
with driver.session() as session:
# Iterate over each airport in the data
        for i,r in airports.iterrows():
                # Create a node for the airport
                session.run("MERGE (:Airport {airport_name: $name, codeIATA: $code, country: $country, city: $city, lat: $lat, lon: $lon})",
                 name=r['airport_name'],
                 code=r['codeIATA'],
                 country=r['country'],
                 city=r['city'],
                 lat=r['lat'],
                 lon=r['lon']
                 )
# Close the driver
driver.close()

##      Flight Request

# Get timestamp
start = datetime.today().strftime('%d%b%y').upper()
end = datetime.today() + timedelta(days=2)
end = end.strftime('%d%b%y').upper()

# Request Lufthansa API
token = requests.post("https://api.lufthansa.com/v1/oauth/token", credentials)
access_token = 'Bearer ' + token.json()['access_token']
headers = {'Authorization':access_token}
response = requests.get(f"https://api.lufthansa.com/v1/flight-schedules/flightschedules/passenger?airlines=LH&startDate={start}&endDate={end}&daysOfOperation=1234567&timeMode=UTC", headers = headers)

df = pd.DataFrame(response.json())
#Unpack flight legs and Period of operation columns
df_legs = df['legs'].apply(pd.Series)
df_op = df['periodOfOperationUTC'].apply(pd.Series)
df = pd.concat((df, df_op, df_legs), axis=1)
flight_list = []

# Flatten flight legs to one row per flight
for i in df_legs:
        leg_df  = df[['airline', 'flightNumber','startDate', 'endDate', i]]
        leg_df = leg_df.dropna(axis = 0)
        unpacked_leg = leg_df[i].apply(pd.Series)
        leg_df =  pd.concat((leg_df, unpacked_leg[['origin', 'destination', 'sequenceNumber',
                'aircraftDepartureTimeUTC', 'aircraftArrivalTimeUTC', 'aircraftType']]), axis = 1)
        leg_df = leg_df.drop(i, axis = 1)
        flight_list.append(leg_df)

clean_df = pd.concat((i for i in flight_list))
clean_df[['startDate', 'endDate']] = clean_df[['startDate', 'endDate']].applymap(lambda x:datetime.strptime(x, '%d%b%y'))

# Duplicate flights that operates on multiple day
df1 = clean_df[clean_df['startDate'] == clean_df['endDate']]
df2 = clean_df[clean_df['startDate'] != clean_df['endDate']]
sub_dfs= []
for gv ,gd in df2.groupby(['airline', 'flightNumber', 'sequenceNumber']):
        gsd = gd['startDate'].min()
        ged = gd['endDate'].max()
        gdr = pd.date_range(gsd, ged, freq = 'd')
        ngd= gd.set_index('startDate').reindex(gdr, method='ffill').reset_index().rename({'index':'startDate'}, axis=1)
        sub_dfs.append(ngd)

df2b = pd.concat(sub_dfs, axis=0)
final_df = pd.concat([df1, df2b])
final_df = final_df.reset_index()

# Format departure and arrival time to neo4j date format
final_df['aircraftDepartureTimeUTC'] = final_df['aircraftDepartureTimeUTC'].apply(lambda x: f'{x//60:02d}:{x%60:02d}')
final_df['aircraftArrivalTimeUTC'] = final_df['aircraftArrivalTimeUTC'].apply(lambda x: f'{x//60:02d}:{x%60:02d}')
final_df['departureTime'] = final_df['startDate'].astype(str) + 'T' + final_df['aircraftDepartureTimeUTC']
final_df['arrivalTime'] = final_df['startDate'].astype(str) + 'T' + final_df['aircraftArrivalTimeUTC']


# Populate DB
driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'neo4jproject'))
with driver.session() as session:
        # Créer des relations entre les nœuds d'aéroport correspondants
        for i,r in final_df.iterrows():
                session.run("""
                        MERGE (a1:Airport {codeIATA: $origin})
                        MERGE (a2:Airport {codeIATA: $destination})
                        MERGE (a1)-[f:FLIGHT {flight_number: $flight_number, airline: $airline, aircraft: $aircraft, STD: $STD, ATD: $ATD}]->(a2)
                        SET f.From = a1.country,
                                f.To = a2.country,
                                f.FromAirportName = a1.airport_name,
                                f.ToAirportName = a2.airport_name
                        """,
                        origin=r["origin"],
                        destination=r["destination"],
                        flight_number=r["flightNumber"],
                        airline=r["airline"],
                        aircraft=r["aircraftType"],
                        STD=r["departureTime"],
                        ATD=r["arrivalTime"]
                        )
