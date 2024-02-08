#for getting product name, brand, mrp, selling price, images
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from swiftshadow.classes import Proxy
from fake_useragent import UserAgent  # New import
import pandas as pd
import time
import os
import re
import json

def find_mrp(soup):
    # Check for different MRP structures
    mrp_div = soup.find("div", {"class": "a-section a-spacing-small aok-align-center"})
    if mrp_div:
        mrp_span = mrp_div.find("span", {"class": "a-offscreen"})
        if mrp_span:
            return mrp_span.get_text(strip=True).replace('₹', '')

    mrp_table = soup.find("table", {"class": "a-lineitem"})
    if mrp_table:
        mrp_td = mrp_table.find("td", string="M.R.P.:")
        if mrp_td and mrp_td.next_sibling:
            mrp_span = mrp_td.next_sibling.find("span", {"class": "a-offscreen"})
            if mrp_span:
                return mrp_span.get_text(strip=True).replace('₹', '')

    # Additional MRP structure
    additional_mrp_div = soup.find("div", {"class": "a-section a-spacing-small aok-align-center"})
    if additional_mrp_div:
        additional_mrp_span = additional_mrp_div.find("span", {"class": "a-size-small aok-offscreen"})
        if additional_mrp_span:
            return additional_mrp_span.get_text(strip=True).replace('₹', '')

    # New code to handle the provided structure
    mrp_span = soup.find("span", {"class": "a-size-small aok-offscreen"})
    if mrp_span:
        return mrp_span.get_text(strip=True).replace('M.R.P.: ₹', '')
    
    # New check for MRP in the provided HTML structure
    basis_price_span = soup.find("span", class_="basisPrice")
    if basis_price_span:
        mrp_text = basis_price_span.get_text(strip=True)
        mrp_match = re.search(r'₹\d+(\.\d+)?', mrp_text)  # Regex to find price format
        if mrp_match:
            return mrp_match.group().replace('₹', '')

    return ""

    

def find_selling_price(soup):
    # Check for different selling price structures
    selling_price_div = soup.find("div", {"class": "a-section a-spacing-none aok-align-center"})
    if selling_price_div:
        selling_price_span = selling_price_div.find("span", {"class": "a-price-whole"})
        if selling_price_span:
            return selling_price_span.get_text(strip=True)

    selling_price_table = soup.find("table", {"class": "a-lineitem"})
    if selling_price_table:
        price_td = selling_price_table.find("td", string=lambda x: x and "Price:" in x)
        if price_td and price_td.next_sibling:
            selling_price_span = price_td.next_sibling.find("span", {"class": "a-offscreen"})
            if selling_price_span:
                return selling_price_span.get_text(strip=True).replace('₹', '')

    # Additional selling price structure
    additional_price_div = soup.find("div", {"class": "a-section a-spacing-none aok-align-center"})
    if additional_price_div:
        additional_price_span = additional_price_div.find("span", {"class": "a-size-large a-color-price"})
        if additional_price_span:
            return additional_price_span.get_text(strip=True).replace('₹', '')

    # Deal of the Day structure
    deal_of_the_day_div = soup.find("div", {"id": "corePrice_desktop"})
    if deal_of_the_day_div:
        deal_price_span = deal_of_the_day_div.find("span", {"class": "a-price a-text-price a-size-medium apexPriceToPay"})
        if deal_price_span:
            deal_price = deal_price_span.find("span", {"class": "a-offscreen"})
            if deal_price:
                return deal_price.get_text(strip=True).replace('₹', '')

    # New structure based on the provided HTML snippet
    core_price_display_div = soup.find("div", {"id": "corePriceDisplay_desktop_feature_div"})
    if core_price_display_div:
        core_price_span = core_price_display_div.find("span", {"class": "a-price aok-align-center reinventPricePriceToPayMargin priceToPay"})
        if core_price_span:
            core_price = core_price_span.find("span", {"class": "a-price-whole"})
            if core_price:
                return core_price.get_text(strip=True)

    return ""

    

def find_product_images(soup):
    images = []

    # Extracting the main image
    main_image_container = soup.find('div', {'id': 'imgTagWrapperId'})
    if main_image_container:
        main_image = main_image_container.find('img')
        if main_image and 'src' in main_image.attrs:
            images.append(main_image['src'])

    # Extracting thumbnail images
    thumbnail_list = soup.find('div', {'id': 'altImages'})
    if thumbnail_list:
        thumbnails = thumbnail_list.find_all('img')
        images.extend([img['src'] for img in thumbnails if 'src' in img.attrs])

    # Extracting images from the script tag data (if available)
    script_tag = soup.find('script', string=re.compile('colorImages'))

    #script_tag = soup.find('script', text=re.compile('colorImages'))
    if script_tag:
        script_content = script_tag.string
        matched_images = re.findall(r'"large":"(https?://[^"]+)"', script_content)
        images.extend(matched_images)

    # Extract additional image URLs from JSON data within script tags
    script_tags = soup.find_all('script', type='text/javascript')
    for script in script_tags:
        if 'colorImages' in script.text:
            json_text = re.search(r'\'colorImages\': { \'initial\': (.+?)\}\},', script.text)
            if json_text:
                json_data = json.loads(json_text.group(1))
                for item in json_data:
                    if 'hiRes' in item and item['hiRes']:
                        images.append(item['hiRes'])
                    elif 'large' in item and item['large']:
                        images.append(item['large'])

    return list(set(images))  # Remove duplicates


def find_product_name(soup):
    product_name_tag = soup.find("span", {"id": "productTitle"})
    return product_name_tag.get_text(strip=True) if product_name_tag else ""

def find_brand(soup):
    # First attempt: Standard location (as previously done)
    brand_row = soup.find("tr", class_="po-brand")
    if brand_row:
        brand_span = brand_row.find("span", class_="po-break-word")
        if brand_span:
            return brand_span.get_text(strip=True)

    # Third attempt: Extract brand from specific anchor tag format
    brand_anchor = soup.find("a", id="bylineInfo")
    if brand_anchor:
        brand_text = brand_anchor.get_text(strip=True)
        # Remove specific prefixes from the brand text
        brand_text = brand_text.replace("Visit the ", "").replace(" Store", "").replace("Brand: ", "")
        return brand_text

    # Additional attempts can be added here based on further observations of the HTML structure

    # If brand is still not found, return an empty string or a default message
    return ""

    


def scrape_amazon_price(product_row, proxy):
    url = product_row.get('amazon_url')
    #if not url or pd.isna(url) or url == 'nan':  # Skip if URL is not present or is NaN
    #    return product_row['Product ID'], product_row['Product Name'], url, '', '', []

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
    chrome_options.add_argument("--no-sandbox")  
    #chrome_options.add_argument("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Initialize UserAgent and select a random user agent
    user_agent = UserAgent()
    random_user_agent = user_agent.random
    chrome_options.add_argument(f'user-agent={random_user_agent}') 
    chrome_options.add_argument(f'--proxy-server={proxy["https"]}')
    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(url)
        WebDriverWait(driver, 18).until(EC.presence_of_element_located((By.ID, "imageBlock")))   #productOverview_feature_div  title_feature_div  apex_desktop ppd imgTagWrapperId imageBlock
        #time.sleep(4)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        product_name = find_product_name(soup)
        brand = find_brand(soup)  # Extract brand
        #mrp = find_mrp(soup)
        #selling_price = find_selling_price(soup)
        #images = find_product_images(soup)

        #return product_row['Product ID'], product_name, url, mrp, selling_price, images
        return product_row['Product ID'], url, product_name, brand
    except Exception as e:
        print(f"Error processing URL {url}: {e}")
        return product_row['Product ID'], url, '',''
        #return product_row['Product ID'], product_name, url, '', '', []
    finally:
        driver.quit()


# Set up proxy rotation
num_proxy = 9
swift = Proxy(countries=['IN', 'PK', 'BD', 'MY', 'TH', 'KR', 'AE', 'DE', 'LK', 'SG'], protocol='https', autoRotate=True, maxProxies=num_proxy, cacheFolder='/Volumes/Hardisc/Unsweet_data/data-managment-main/cachefolder')

# Read the processed CSV file
csv_file_path = '/Volumes/Hardisc/Unsweet_data/data-managment-main/get_brand_15000.csv'  #hair-with-quotes.csv  makeup_missing_images_pricelink.csv
df = pd.read_csv(csv_file_path) 

# Define output columns including images and the product URL
#output_columns = ['Product ID', 'Product Name', 'Product URL', 'MRP', 'Selling Price', 'Images']
output_columns = ['Product ID', 'Product URL', 'Product Name', 'Brand']

output_file = '/Volumes/Hardisc/Unsweet_data/data-managment-main/amazon_getbrand_15000.csv'

# Create or append to the output CSV file
if not os.path.exists(output_file):
    pd.DataFrame(columns=output_columns).to_csv(output_file, index=False)

# Use ThreadPoolExecutor for parallel execution
with ThreadPoolExecutor(max_workers=9) as executor:
    for product_row in df.to_dict('records'):
        executor.submit(lambda row: pd.DataFrame([scrape_amazon_price(row, swift.proxy())], columns=output_columns).to_csv(output_file, mode='a', index=False, header=False), product_row)

print("Scraping completed and data saved to", output_file)
