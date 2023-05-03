from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import Depends, FastAPI, Header, HTTPException, Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from neo4j import GraphDatabase 
from datetime import datetime, timezone, timedelta
import requests
import configparser

app = FastAPI(title="Lufthansa API",
              description="API to get information about Lufthansa flights",
              version="1.0.1")

driver = GraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "neo4jproject"))

# Définir le dictionnaire d'utilisateurs et de mots de passe
users = {
    "sabrine": "sab_project23",
    "maryem": "mar_project23",
    "eloi": "eloi_project_23",
    "remy": "remy_project23"
}

security = HTTPBasic()

config = configparser.ConfigParser()
config.read('config.ini')
client_id = config.get('credentials', 'client_id')
client_secret = config.get('credentials', 'client_secret')
credentials = {'client_id':client_id, 'client_secret':client_secret,'grant_type':'client_credentials'}


@app.get("/health")
def health_check():
    return {"status": "ok"}    
 
def root(credentials: HTTPBasicCredentials = Depends(security)):
    """
    This function is used for authentification
    """
    username = credentials.username
    password = credentials.password

    if username not in users or users[username] != password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return {"message": "Authorized"}
@app.get("/airports")
def get_airports(root = Depends(root)):
    with driver.session() as session:
        result = session.run("MATCH (a:Airport) RETURN a")
        airports = [record for record in result]
        return {"airports": airports}

# Définition de l'endpoint pour récupérer les informations sur les vols d'aujourd'hui
@app.get('/flights/today')
def get_flights_today(root = Depends(root)):
    # Récupérer et formater la date d'aujourd'hui
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow = tomorrow.strftime("%Y-%m-%d")
    with driver.session() as session:
        # Récupérer les informations de vol pour aujourd'hui
        result = session.run("""
            MATCH (a1:Airport)-[f:FLIGHT]->(a2:Airport)
            WHERE a1.codeIATA <> a2.codeIATA AND f.STD > $today AND f.STD < $tomorrow
            RETURN {flight_number: f.flight_number, airline: f.airline, aircraft: f.aircraft, STD: f.STD, ATD: f.ATD, From: f.From, To: f.To, DepartAirport: f.FromAirportName, ArrivalAirport: f.ToAirportName} as flight""",
            today=today,
            tomorrow=tomorrow)
        # Convertir le résultat en une liste de dictionnaires
        flights = [record['flight'] for record in result]
        return JSONResponse(content=flights)

# Définition de l'endpoint pour récupérer les informations sur les vols lié à un aéroport
@app.get('/departures/{IATA}')
def get_departures(IATA, root = Depends(root)):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')
    with driver.session() as session:
        result = session.run("""
            MATCH (a1:Airport)-[f:FLIGHT]->(a2:Airport)
            WHERE a1.codeIATA = $IATA AND f.STD > $now
            RETURN {flight_number: f.flight_number, airline: f.airline, aircraft: f.aircraft, STD: f.STD, ATD: f.ATD, From: f.From, To: f.To, DepartAirport: f.FromAirportName, ArrivalAirport: f.ToAirportName} as flight
            ORDER BY f.STD
            LIMIT 5""",
            IATA=IATA,
            now=now)
        flights = [record['flight'] for record in result]
        return JSONResponse(content=flights)

@app.get('/arrivals/{IATA}')
def get_arrivals(IATA, root = Depends(root)):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')
    with driver.session() as session:
        result = session.run("""
            MATCH (a1:Airport)-[f:FLIGHT]->(a2:Airport)
            WHERE a2.codeIATA = $IATA AND f.ATD > $now
            RETURN {flight_number: f.flight_number, airline: f.airline, aircraft: f.aircraft, STD: f.STD, ATD: f.ATD, From: f.From, To: f.To, DepartAirport: f.FromAirportName, ArrivalAirport: f.ToAirportName} as flight
            ORDER BY f.ATD
            LIMIT 5""",
            IATA=IATA,
            now=now)
        flights = [record['flight'] for record in result]
        return JSONResponse(content=flights)
       
@app.get('/flight_status/{flightNumber}')
def get_flight_status(flightNumber, root = Depends(root)):
	token = requests.post("https://api.lufthansa.com/v1/oauth/token", credentials)
	access_token = 'Bearer ' + token.json()['access_token']
	headers = {'Authorization':access_token}
	today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
	response = requests.get(f"https://api.lufthansa.com/v1/operations/flightstatus/{flightNumber}/{today}", headers = headers)
	if response.ok:
		return response.json()
	else: raise HTTPException(status_code=404, detail="Invalid flight number")
        
@app.get("/flights_by_route")
def get_flights(origin:str, destination:str, root = Depends(root)):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')
    with driver.session() as session:
        result = session.run("""
        MATCH (a1:Airport)-[f:FLIGHT]->(a2:Airport) 
        WHERE a1.codeIATA = $origin AND a2.codeIATA = $destination AND f.STD > $now
        RETURN {flight_number: f.flight_number, airline: f.airline, aircraft: f.aircraft, STD: f.STD, ATD: f.ATD, From: f.From, To: f.To, DepartAirport: f.FromAirportName, ArrivalAirport: f.ToAirportName} as flight
        ORDER BY f.STD
        LIMIT 5""",
        origin=origin, destination=destination, now=now)
        flights = [record for record in result]
        if not flights:
            return {"message": "No flights found between {} and {}".format(origin, destination)}
        else:
            return {"flights": flights}
