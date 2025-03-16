import sys
import importlib
import scrapelib
from bs4 import BeautifulSoup
from dateutil import parser
import re
import csv
from datetime import date, timedelta, datetime
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cnn_transcript_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define columns for the CSV output
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

# Output file configuration
output_dir = "../data/cnn_transcripts_recent"
current_date = datetime.now().strftime("%Y%m%d")
csv_file = os.path.join(output_dir, f"cnn_transcripts_{current_date}.csv")

def extract_transcript(html):
    """Extract transcript content from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    cnnTransStoryHead = soup.find('p', {"class": "cnnTransStoryHead"})
    cnnTransSubHead = soup.find('p', {"class": "cnnTransSubHead"})
    
    content = ""
    date_obj = None
    tz = None
    
    for a in soup.find_all('p', {"class": "cnnBodyText"}):
        text = a.text
        m = re.match(
            r"Aired (.*\s+\d{1,2},\s+\d{4}\s+-\s+\d{2}:\d{2}).*([A-Z]{2,3})$", text)
        if m:
            date_str = m.group(1)
            tz = m.group(2)
            try:
                date_obj = parser.parse(date_str)
            except Exception as e:
                logger.error(f"Error parsing date: {e}")
                try:
                    date_str = date_str.split('-')[0]
                    date_obj = parser.parse(date_str)
                except Exception as e2:
                    logger.error(f"Second attempt failed: {e2}")
            logger.debug(f"Parsed date: {date_obj}, Timezone: {tz}")
        elif text.startswith("THIS IS A RUSH TRANSCRIPT."):
            pass
        else:
            content = text
    
    data = {}
    try:
        if cnnTransStoryHead:
            data['program.name'] = cnnTransStoryHead.text
        else:
            data['program.name'] = "Unknown Program"
            
        data['channel.name'] = 'CNN'
        
        if date_obj:
            data['year'] = date_obj.year
            data['month'] = date_obj.month
            data['date'] = date_obj.day
            data['time'] = f"{date_obj.hour:02d}:{date_obj.minute:02d}"
            data['timezone'] = tz if tz else "Unknown"
        
        if cnnTransSubHead:
            data['subhead'] = cnnTransSubHead.text
        else:
            data['subhead'] = ""
            
        data['text'] = content
        
        # Calculate word count
        data['wordcount'] = len(content.split()) if content else 0
        
    except Exception as e:
        logger.error(f"Error extracting transcript data: {e}")
    
    return data

def load_progress_from_csv():
    """
    Load progress information from the existing CSV file.
    Returns:
        - Set of already processed URLs
        - Date to resume from
    """
    processed_urls = set()
    latest_date = date(2022, 2, 1)  # Default start date
    
    if not os.path.exists(csv_file):
        logger.info(f"No existing CSV file found at {csv_file}. Starting from {latest_date}")
        return processed_urls, latest_date
    
    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Track processed URLs
                if 'url' in row and row['url']:
                    processed_urls.add(row['url'])
                
                # Track latest date
                try:
                    if all(k in row for k in ['year', 'month', 'date']):
                        row_date = date(
                            int(row['year']), 
                            int(row['month']), 
                            int(row['date'])
                        )
                        # Use the URL date rather than the transcript air date
                        # Extract date from URL pattern /TRANSCRIPTS/YYYY.MM.DD/program.html
                        url_parts = row['url'].split('/')
                        if len(url_parts) >= 3:
                            date_part = url_parts[-2]
                            if '.' in date_part and len(date_part.split('.')) == 3:
                                year, month, day = map(int, date_part.split('.'))
                                url_date = date(year, month, day)
                                if url_date > latest_date:
                                    latest_date = url_date
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse date from row: {e}")
        
        if processed_urls:
            logger.info(f"Loaded {len(processed_urls)} already processed URLs from CSV")
            logger.info(f"Resuming from {latest_date}")
        
    except Exception as e:
        logger.error(f"Error loading existing CSV: {e}")
    
    return processed_urls, latest_date

def main():
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load progress from existing CSV
    processed_urls, startdate = load_progress_from_csv()
    
    # Determine file mode: 'w' for new file, 'a' for append
    file_mode = 'a' if os.path.exists(csv_file) else 'w'
    
    # Open CSV file for writing
    f = open(csv_file, file_mode, newline='', encoding='utf-8')
    writer = csv.DictWriter(f, fieldnames=columns, dialect='excel')
    
    # Write header only for new files
    if file_mode == 'w':
        writer.writeheader()
    
    # Initialize scraper with rate limiting
    s = scrapelib.Scraper(requests_per_minute=60)
    
    # Set end date to today
    enddate = date.today()
    
    # Track progress
    total_days = (enddate - startdate).days + 1
    current_day = 1
    
    try:
        # Loop through each day in the date range
        current_date = startdate
        while current_date <= enddate:
            logger.info(f"Processing day {current_day}/{total_days}: {current_date.year}-{current_date.month:02d}-{current_date.day:02d}")
            
            # Construct URL for the day's transcripts
            day_url = f'http://transcripts.cnn.com/TRANSCRIPTS/{current_date.year}.{current_date.month:02d}.{current_date.day:02d}.html'
            
            try:
                # Get the main page for the day
                res = s.get(day_url)
                soup = BeautifulSoup(res.text, "html.parser")
                logger.info(f"Page title: {soup.title.text if soup.title else 'No title'}")
                
                # Find all transcript sections
                transcript_sections = soup.find_all("div", {"class": "cnnTransDate"})
                if not transcript_sections:
                    logger.warning(f"No transcript sections found for {current_date}")
                
                for a in transcript_sections:
                    logger.info(f"Processing transcript section: {a.text.strip()}")
                    
                    # Get the sibling div that contains the links
                    soup2 = a.find_next_siblings('div')
                    if not soup2:
                        logger.warning("No transcript links found in this section")
                        continue
                    
                    soup2 = soup2[0]
                    
                    # Extract all transcript links
                    links = soup2.find_all("a")
                    if not links:
                        logger.warning("No links found in this section")
                        continue
                        
                    logger.info(f"Found {len(links)} transcripts in this section")
                    
                    for link in links:
                        url = 'http://transcripts.cnn.com' + link['href']
                        
                        # Skip if already processed
                        if url in processed_urls:
                            logger.info(f"Skipping already processed: {url}")
                            continue
                        
                        logger.info(f"Processing transcript: {url}")
                        
                        try:
                            # Get the transcript page
                            res2 = s.get(url)
                            
                            # Extract transcript data
                            data = extract_transcript(res2.text)
                            data['url'] = url
                            
                            # Generate a unique ID using the URL
                            data['uid'] = url.split('/')[-1].replace('.html', '')
                            
                            # Set path based on URL structure
                            data['path'] = '/'.join(url.split('/')[-2:])
                            
                            # Write to CSV
                            writer.writerow(data)
                            f.flush()  # Ensure data is written immediately
                            
                            # Add to processed URLs
                            processed_urls.add(url)
                            
                            logger.info(f"Successfully processed: {data.get('program.name', 'Unknown')}")
                            
                        except Exception as e:
                            logger.error(f"Error processing transcript {url}: {e}")
            
            except Exception as e:
                logger.error(f"Error processing day {current_date}: {e}")
            
            # Move to next day
            current_date += timedelta(days=1)
            current_day += 1
    
    finally:
        # Ensure file is closed even if there's an error
        f.close()
        logger.info(f"Scraping completed. Results saved to {csv_file}")

if __name__ == "__main__":
    logger.info("Starting CNN transcript scraper")
    main()