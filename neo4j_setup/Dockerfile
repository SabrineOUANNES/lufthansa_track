FROM python:3.9-slim-buster
WORKDIR /src
COPY . /src
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT ["python3"]
CMD ["main.py"]
