FROM  apache/spark:3.5.3-python3

USER root

# Install Python dependencies
RUN pip3 install --no-cache-dir pyspark==3.5.3

RUN mkdir -p /opt/spark/jobs && chmod 755 /opt/spark/jobs

# Copy spark jobs
COPY jobs/*.py /opt/spark/jobs

#Run permissions
RUN chmod -R 755 /opt/spark/jobs

USER spark

WORKDIR /opt/spark/jobs


