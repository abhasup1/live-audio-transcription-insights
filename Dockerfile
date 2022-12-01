FROM python:3.8

WORKDIR /app/

RUN mkdir /app/requirements
COPY requirements.txt /app/requirements

RUN pip install `find "requirements/" -mindepth 1 -maxdepth 1 -type f -print0 | xargs -0 -I {} echo "-r {}"`

COPY templates /app/templates
COPY config /app/config
COPY main.py /app/
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]