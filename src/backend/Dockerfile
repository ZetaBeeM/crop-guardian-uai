FROM python:3.12-slim
WORKDIR /backend
#Selecting /backend as the working directory.
COPY requirements.txt requirements.txt
#Copying the requirements.txt file to the working directory.
RUN pip3 install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "180", "app:app"]
