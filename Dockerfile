# Copyright IBM Corp. 2024
#
FROM python:3


USER root

#
WORKDIR /code

#
COPY ./requirements.txt /code/requirements.txt

#
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

#
COPY ./src/app /code


#
CMD ["uvicorn", "main:app", "--host=0.0.0.0", "--port=8000"]
