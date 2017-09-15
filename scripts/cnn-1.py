import sys
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
    soup = BeautifulSoup(html)

    for td in soup.find_all('td'):
       h2 = td.find('h2')
       if h2:
           cnnTransStoryHead = h2.text
           h3 = td.find('h3')
           if h3:
               cnnTransSubHead = h3.text
               print cnnTransSubHead
               text = h3.next_sibling
               text = text.strip()
               m = re.match(r"Aired (.*\s+\d{1,2},\s+\d{4}\s+-\s+\d{1,2}:\d{2}.*)\s+([A-Z]{2,3})$", text)
               if m:
                  date = m.group(1)
                  tz = m.group(2)
                  date = parser.parse(date)
                  print date, tz

               for p in h3.find_next_siblings('p'):
                  paragraphs = p.text.split('\n')
                  break
               if len(paragraphs) == 1:
                   paragraphs = []
                   for p in h3.find_next_siblings('p'):
                      paragraphs += p.text.split('\n')
               lines = []
               for l in paragraphs:
                   text = l.strip()
                   if text.find('THIS IS A RUSH TRANSCRIPT') != -1:
                       continue
                   #if text.find('TO ORDER A VIDEO OF THIS TRANSCRIPT') != -1:
                   #    continue
                   lines.append(text)
               content = '\n'.join(lines)
           else:
               h4 = td.find('h4')
               if h4:
                   cnnTransSubHead = h4.text
                   print cnnTransSubHead
                   text = h4.next_sibling
                   text = text.strip()
                   m = re.match(r"Aired (.*\s+\d{1,2},\s+\d{4}\s+-\s+\d{1,2}:\d{2}.*)\s+([A-Z]{2,3})$", text)
                   if m:
                       date = m.group(1).strip()
                       tz = m.group(2)
                       date = parser.parse(date)
                       print date, tz
                   p = h4.next_sibling.next_sibling
                   content = p.text.replace('THIS IS A RUSH TRANSCRIPT. THIS COPY MAY NOT BE IN ITS FINAL FORM AND MAY BE UPDATED.', '').strip()
                   #print content
           break

    data = {}
    try:
        print date
        data['channel.name'] = 'WWW'
        data['program.name'] = cnnTransStoryHead
        data['year'] = date.year
        data['month'] = date.month
        data['date'] = date.day
        data['time'] = "%02d:%02d" % (date.hour, date.minute)
        data['timezone'] = tz
        data['subhead'] = cnnTransSubHead
        data['text'] = content
    except Exception as e:
        print e
    return data


if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding("utf-8")

    f = open("cnn.csv", "ab")
    writer =csv.DictWriter(f, fieldnames=columns, dialect='excel')

    writer.writeheader()

    s = scrapelib.Scraper(requests_per_minute=60)

    #startdate = date(2000, 1, 1)
    #startdate = date(2000, 4, 22)
    #startdate = date(2001, 4, 4)
    startdate = date(2002, 8, 7)

    # Will be throttled to 10 HTTP requests per minute
    i = 0
    while True:
        print startdate.year, startdate.month, startdate.day
        res = s.urlopen('http://transcripts.cnn.com/TRANSCRIPTS/%04d.%02d.%02d.html' %
                        (startdate.year, startdate.month, startdate.day))
        soup = BeautifulSoup(res)
        print soup.title
        try:
            for a in soup.find_all("li"):
                l = a.find('a')
                url = l['href']
                if not url.startswith('http://'):
                    url = 'http://transcripts.cnn.com' + url 
                try:
                    i += 1
                    print("#%d: %s" % (i, url))
                    res2 = s.urlopen(url)
                    data = extract_transcript(res2)
                    data['url'] = url
                    writer.writerow(data)
                except Exception as e:
                    print e
                    print url, res2.response
                print("Inner Break")
                #break
        except Exception as e:
            print "ERROR: %s" % e
        startdate += timedelta(days=1)
        if startdate == date(2002, 9, 17):
            print "Complete..."
            break
    f.close()
