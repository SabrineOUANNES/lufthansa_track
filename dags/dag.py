from airflow import DAG
from airflow.operators.python import PythonOperator
from neo4j import GraphDatabase
import csv
import requests
from datetime import datetime, timedelta
import io
import configparser
import pandas as pd

config = configparser.ConfigParser()
config.read('/opt/airflow/dags/config.ini')
client_id = config.get('credentials', 'client_id')
client_secret = config.get('credentials', 'client_secret')

dag_airport = DAG(
    dag_id='airports_DAG',
    description='Mise a jour régulière de la base de données via le site Data.World',
    tags=['projet'],
    schedule_interval='0 0 1 * *',
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2023, 4, 24),
    },
    catchup = False,
    doc_md= '''#Data.World DAG
    Request Data.World for airports
    '''
)

def get_airports_data(): 
    response = requests.get("https://query.data.world/s/iizp6mghtd73iij65xv5imaavvhr6p?dws=00000")
    airports = []
    if response.status_code == 200:
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
    driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'neo4jproject'))
    with driver.session() as session:
    # Iterate over each airport in the data
        for airport in airports:
            # Create a node for the airport
            session.run("MERGE (:Airport {airport_name: $name, codeIATA: $code, country: $country, city: $city, lat: $lat, lon: $lon})",
             name=airport['airport_name'], 
             code=airport['codeIATA'],
             country=airport['country'],
             city=airport['city'],
             lat=airport['lat'],
             lon=airport['lon']
             )        
    # Close the driver
    driver.close()

task1 = PythonOperator(
    task_id='request_airport',
    python_callable=get_airports_data,
    dag=dag_airport,
    doc_md='''#Request API
    Retrieve airport data from data.world API and return as a list of dictionaries.
    Each dictionary represents an airport with keys for the airport name, IATA code,
    country, city, latitude, and longitude. 
    '''
)

dag_flight = DAG(
    dag_id='flights_DAG',
    description='Mise a jour régulière de la base de données via l\'API Lufthansa',
    tags=['projet'],
    schedule_interval='0 1 * * *',
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2023, 4, 24),
    },
    catchup = False,
    doc_md= '''#Data.World DAG
    Request Data.World for airports
    '''
)

def convert_to_neo4j_date(date, time): 
    date_obj = datetime.strptime(date, '%d%b%y')
    date = date_obj.strftime('%Y-%m-%d')
    hour = time // 60
    minute = time % 60
    return f"{date}T{hour:02d}:{minute:02d}"

def get_flights_data():
    start = datetime.today().strftime('%d%b%y').upper()
    end = datetime.today() + timedelta(days=2)
    end = end.strftime('%d%b%y').upper()
    
    # Get data from Lufthansa API
    credentials = {'client_id':client_id, 'client_secret':client_secret,'grant_type':'client_credentials'}
    token = requests.post("https://api.lufthansa.com/v1/oauth/token", credentials)
    access_token = 'Bearer ' + token.json()['access_token']
    headers = {'Authorization':access_token}
    response = requests.get(f"https://api.lufthansa.com/v1/flight-schedules/flightschedules/passenger?airlines=LH&startDate={start}&endDate={end}&daysOfOperation=1234567&timeMode=UTC", headers = headers)
    df = pd.DataFrame(response.json())
    
    #Unpack flight legs and period of operation 
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
    
    # Delete previous data
    driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'neo4jproject'))
    with driver.session() as session: 
            session.run("""
                    MATCH (a)-[f:FLIGHT]-(a2)
                    DELETE f
                    """)
    # Import new data 
    with driver.session() as session:
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

    driver.close()    

task2 = PythonOperator(
    task_id='request_flight',
    python_callable=get_flights_data,
    dag=dag_flight,
    doc_md='''#Request API
    Retrieve flights data from Lufthansa API
    '''
)
