FROM python:3.9

RUN mkdir /opt/rss
WORKDIR /opt/rss
ADD . .

RUN pip install requests feedparser you-get

CMD python src/main.py
