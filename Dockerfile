FROM python:3.10

WORKDIR /code

RUN apt update

#RUN pip install --upgrade pip

# Install app
COPY ./requirements.txt /code/requirements.txt
RUN pip install -r /code/requirements.txt

COPY ./tesla_mcp /code/tesla_mcp

EXPOSE 80
CMD ["uvicorn", "tesla_mcp.app:app", "--host", "0.0.0.0", "--port", "80"]