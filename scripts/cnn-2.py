import sys
import importlib
import scrapelib
from bs4 import BeautifulSoup
from dateutil import parser
import re
import csv
from datetime import date, timedelta

columns = ['url',
           'channel.name',
           'program.name',
           'uid',
           'duration',
           'year',
           'month',
           'date',
           'time',
           'timezone',
           'path',
           'wordcount',
           'subhead',
           'text']


def extract_transcript(html):
    soup = BeautifulSoup(html, "html.parser")
    cnnTransStoryHead = soup.find('p', {"class": "cnnTransStoryHead"})
    # print cnnTransStoryHead.text
    cnnTransSubHead = soup.find('p', {"class": "cnnTransSubHead"})
    # print cnnTransSubHead.text
    # print html
    #body = soup.find('p', {"class": "cnnBodyText"})
    # print body.text

    for a in soup.find_all('p', {"class": "cnnBodyText"}):
        text = a.text
        m = re.match(
            r"Aired (.*\s+\d{1,2},\s+\d{4}\s+-\s+\d{2}:\d{2}).*([A-Z]{2,3})$", text)
        if m:
            date = m.group(1)
            tz = m.group(2)
            date = parser.parse(date)
            print(date, tz)
        elif text.startswith("THIS IS A RUSH TRANSCRIPT."):
            pass
        else:
            content = text

    data = {}
    try:
        print(date)

        data['channel.name'] = 'WWW'
        data['program.name'] = cnnTransStoryHead.text
        data['year'] = date.year
        data['month'] = date.month
        data['date'] = date.day
        data['time'] = "%02d:%02d" % (date.hour, date.minute)
        data['timezone'] = tz
        data['subhead'] = cnnTransSubHead.text
        data['text'] = content
    except Exception as e:
        print(e)
    return data


if __name__ == "__main__":
    importlib.reload(sys)

    # sys.setdefaultencoding("utf-8")
    if (sys.stdout.encoding != 'utf-8'):
        sys.stdout.encoding = 'utf-8'

    f = open("cnn.csv", "a")
    writer = csv.DictWriter(f, fieldnames=columns, dialect='excel')

    writer.writeheader()

    s = scrapelib.Scraper(requests_per_minute=60)

    startdate = date(2014, 6, 18)

    # Will be throttled to 10 HTTP requests per minute
    while True:
        print(startdate.year, startdate.month, startdate.day)
        res = s.get('http://transcripts.cnn.com/TRANSCRIPTS/%04d.%02d.%02d.html' %
                    (startdate.year, startdate.month, startdate.day))

        soup = BeautifulSoup(res.text, "html.parser")
        print(soup.title)
        for a in soup.find_all("div", {"class": "cnnTransDate"}):
            print(a)
            soup2 = a.find_next_siblings('div')[0]
            # for b in soup2.find_all("div", {"class": "cnnSectBulletItems"}):
            for link in soup2.find_all("a"):
                url = 'http://transcripts.cnn.com' + link['href']
                print(url)
                try:
                    res2 = s.get(url)
                    data = extract_transcript(res2.text)
                    data['url'] = url
                    writer.writerow(data)
                except Exception as e:
                    print(e)
                    print(url, res2.response)
                print("Inner Break")
                # break
            print("Outer Break")
            # break
        startdate += timedelta(days=1)
    f.close()
