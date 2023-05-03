**Lufthansa Tracker**

## Presentation

This repository contains the code for our project **Lufthansa Tracker** , developed during our [Data Scientist training](https://datascientest.com/en/data-engineer-course) at [DataScientest](https://datascientest.com/).

The goal of this project is to gather and display flights data based on [Lufthansa Open API](https://developer.lufthansa.com/docs). 
To do so several Docker container are created that compose the application:
  
- Neo4J  
- FastAPI
- Dash Application
- Airflow

**Lufthansa Tracker** can:

- Display next departures and arrivals for an airport
- Display fight route and next flights between an origin and a destination airport
- Estimate flight position based on flight status information

This project was developed by the following team :

- Sabrine OUANESS ([GitHub](https://github.com/SabrineOUANNES) / [LinkedIn](https://www.linkedin.com/in/sabrine-ouannes/))
- Maryem MIFTAH ([GitHub](https://github.com/MaryemKhair))
- Eloi CHATEAU ([GitHub](https://github.com/eloi-cht) / [LinkedIn](https://www.linkedin.com/in/eloi-chateau/))

##  Installation and Usage

Airflow need at least 4 GB RAM to run so for all containers to run properly you need at least 8 GB RAM
Following installation steps are for Linux system, you need docker installed.

To install the application run following command
```shell
mkdir -p ./dags ./logs ./plugins  
echo -e "AIRFLOW_UID=$(id -u)\nAIRFLOW_GID=0" > .env  
docker-compose up airflow-init  
docker-compose up
```


Once it's launched the app should then be available at [localhost:5000](http://localhost:5000).
