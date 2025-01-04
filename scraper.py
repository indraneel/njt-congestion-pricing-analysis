import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import pytz
import argparse
import os
from typing import List, Dict

class NJTransitScraper:
    URLS = {
        'secaucus_upper': 'https://www.njtransit.com/dv-to/Secaucus%20Junction%20Upper%20Level',
        'secaucus_lower': 'https://www.njtransit.com/dv-to/Secaucus%20Junction%20Lower%20Level',
        'newark': 'https://www.njtransit.com/dv-to/Newark%20Penn%20Station',
        'watsessing': 'https://www.njtransit.com/dv-to/Watsessing%20Avenue%20Station',
        'maplewood': 'https://www.njtransit.com/dv-to/Maplewood%20Station'
    }

    def __init__(self, destination_filter: str = None):
        self.destination_filter = destination_filter
        self.eastern_tz = pytz.timezone('America/New_York')

    def get_current_file_date(self) -> str:
        """Get the current date for file naming, accounting for 4am boundary"""
        now = datetime.datetime.now(self.eastern_tz)
        if now.hour < 4:
            # If it's before 4am, use previous day's date
            now = now - datetime.timedelta(days=1)
        return os.path.join('departures', now.strftime('%Y-%m-%d'))

    def parse_occupancy(self, item) -> Dict:
        """Parse occupancy information for each train car section"""
        occupancy_info = {
            'total_sections': 0,
            'light': 0,
            'medium': 0,
            'heavy': 0,
            'no_data': 0
        }

        occupancy_section = item.find('ol', {'data-v-5d9f6349': True, 'class': 'list-inline d-inline-block align-self-end m-0 cur--pointer'})
        if not occupancy_section:
            return occupancy_info

        sections = occupancy_section.find_all('li', {'data-v-b5fd45da': True})
        occupancy_info['total_sections'] = len(sections)

        for section in sections:
            dots = section.find_all('li', {'data-v-8927eb98': True})
            for dot in dots:
                style = dot.get('style', '')
                if 'background-color: rgb(11, 102, 35)' in style:  # Light
                    occupancy_info['light'] += 1
                elif 'background-color: rgb(255, 193, 7)' in style:  # Medium 
                    occupancy_info['medium'] += 1
                elif 'background-color: rgb(220, 53, 69)' in style:  # Heavy
                    occupancy_info['heavy'] += 1
                else:
                    occupancy_info['no_data'] += 1

        return occupancy_info

    def scrape_departures(self, url: str, station: str) -> List[Dict]:
        """Scrape departure information from a single URL"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            departures = []
            for item in soup.find_all('li', {'data-v-403a649a': True, 'class': 'border'}):
                try:
                    destination = item.find('strong', {'data-v-403a649a': True}).text.strip()
                    
                    if self.destination_filter and self.destination_filter.lower() not in destination.lower():
                        continue
                    
                    # Get line (e.g., NEC, MOBO)
                    line = item.find('span', {'data-v-403a649a': True}).text.strip()
                    
                    # Get train number
                    train_text = item.find(text=lambda t: t and 'Train' in t)
                    train_number = train_text.strip().replace('Train', '').strip() if train_text else ''
                    
                    # Get departure time
                    time_element = item.find('strong', {'class': 'h2'})
                    departure_time = time_element.text.strip() if time_element else ''
                    
                    # Get status (e.g., "All Aboard", "On Time")
                    status_element = item.find('strong', {'class': 'h3'})
                    status = status_element.text.strip() if status_element else ''
                    
                    # Get track number
                    track_text = item.find(text=lambda t: t and 'Track' in t)
                    track = track_text.strip().replace('Track', '').strip() if track_text else ''
                    
                    # Get occupancy information
                    occupancy = self.parse_occupancy(item)
                    
                    timestamp = datetime.datetime.now(self.eastern_tz).strftime('%Y-%m-%d %H:%M:%S')
                    
                    departures.append({
                        'timestamp': timestamp,
                        'station': station,
                        'destination': destination,
                        'line': line,
                        'train_number': train_number,
                        'departure_time': departure_time,
                        'status': status,
                        'track': track,
                        'car_sections': occupancy['total_sections'],
                        'occupancy_light': occupancy['light'],
                        'occupancy_medium': occupancy['medium'],
                        'occupancy_heavy': occupancy['heavy'],
                        'occupancy_no_data': occupancy['no_data']
                    })
                    
                except Exception as e:
                    print(f"Error parsing departure item: {e}")
                    continue
                    
            return departures
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return []

    def save_to_csv(self, departures: List[Dict]):
        """Save departures to daily CSV file"""
        if not departures:
            return

        date = self.get_current_file_date()
        directory = os.path.dirname(date)  # Get the directory part of the path
        filename = os.path.join(directory, f'departures_{os.path.basename(date)}.csv')
        
        # Ensure the directory exists
        os.makedirs(directory, exist_ok=True)
        
        df = pd.DataFrame(departures)
        
        # If file exists, append without header
        if os.path.exists(filename):
            df.to_csv(filename, mode='a', header=False, index=False)
        else:
            df.to_csv(filename, index=False)


    def run(self):
        """Run the scraper for all stations"""
        all_departures = []
        
        for station_key, url in self.URLS.items():
            station_name = station_key.replace('_', ' ').title()
            departures = self.scrape_departures(url, station_name)
            all_departures.extend(departures)
            
        self.save_to_csv(all_departures)

def main():
    parser = argparse.ArgumentParser(description='NJ Transit DepartureVision Scraper')
    parser.add_argument('--destination', type=str, help='Filter by destination')
    args = parser.parse_args()
    
    scraper = NJTransitScraper(destination_filter=args.destination)
    scraper.run()

if __name__ == '__main__':
    main()