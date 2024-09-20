from flask import Flask, render_template, request , send_file , jsonify
import os
import requests
from bs4 import BeautifulSoup
from langchain_community.utilities import GoogleSerperAPIWrapper
from openai import AzureOpenAI
from selenium import webdriver
import time
import re
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import csv
import ast
from csv import DictWriter
import rocketreach
import os


rr = rocketreach.Gateway(api_key="154f467k3381258aa968f640d89638c71bbf1bec")
result_rocket_reach = rr.account.get()
os.environ["SERPER_API_KEY"] = "3cca4e86a4d3e468b0db1c9e6438b4701daad293"
client = AzureOpenAI(
  api_key="c18c9011aa0746d78cd93f07da587452",
  api_version="2024-02-01",
  azure_endpoint="https://gpt4o-adya.openai.azure.com/"
)
search = GoogleSerperAPIWrapper(gl='in')
app = Flask(__name__)


def read_csv(file_path):
    companies = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            companies.append(row)
    return companies

def scrape_content_bs(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup.get_text(separator=" ", strip=True)
        else:
            print(f"Failed to fetch data from {url}. HTTP Status Code: {response.status_code}")
            return ""
    except Exception as e:
        print(f"An error occurred while fetching data from {url}: {e}")
        return ""
    
def scrape_content(url):
    content = scrape_content_bs(url)
    return content

def clean_text(text):
    text = text.replace('\n', ' ')
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def split_text_into_chunks(text, word_count):
    words = re.split(r'\s+', text)
    chunks = [' '.join(words[i:i + word_count]) for i in range(0, len(words), word_count)]
    print("chunk",chunks)
    return chunks


def company_names(text):
    """Extract names of Indian Retail companies from the given text"""
    company_name_list = {
        "Input_text": text,
        "Company names": ["Apple",'Google','Microsoft',"Reliance Retail", "Future Retail", "Avenue Supermarts"]
    }
    return json.dumps(company_name_list)

def extract_company_names(list_of_company_names):
    tools = [
    {
        "type": "function",
        "function": {
            "name": "company_names",
            "description": "Extract names of Indian Retail companies from the given list_of_company_names",
            "parameters": {
                "type": "object",
                "properties": {
                    "list_of_company_names": {
                        "type": "string",
                        "description": "The list_of_company_names containing company names",
                        "items": {
                            "type": "array",
                            "description": "The name of the Indian Retail company"
                        }
                    }
                },
                "required": ["list_of_company_names"],
            },
        }
    }
    ]
    messages = [
        {
            "role": "system",
            "content": "You are an AI bot that helps in extracting the Company names"
        },
    {
        "role": "user",
        "content": "Extract the names of Indian Retail companies from the following text:\n\n" + list_of_company_names
    }
]
    response = client.chat.completions.create(
        model="gpt4o_deployment",
        messages=messages,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        tools=tools
    )

    return response.choices[0].message

def validate_company_names(extracted_names):

    prompt_template = """
    ### Role:
    You are an intelligent Bot that helps to Extract the Company Names.

    ### Task:
    The following list contains names of companies. Please verify if each company name is valid. If a company name does not meet this criterion, it should be removed from the list .

    Extracted Company Names:
    {extracted_names}

    Guidelines:
    - Return the list of valid company names.

    Example:
    - Valid: "ABC Retail Limited", "XYZ Corporation Pvt Ltd"
    - Invalid: "Retail", "XYZ Corp" , 'htmlheadmeta'

    Verified Company Names:
    """
    prompt = prompt_template.format(extracted_names=', '.join(extracted_names))

    messages = [
        {"role": "system", "content": "You are an AI bot that helps in extracting the Company names"},
        {"role": "user", "content": prompt}
    ]
    response_company = client.chat.completions.create(
        model="gpt4o_deployment",
        messages=messages,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    return response_company.choices[0].message.content

def clean_extracted_name(validated_names): 
    lines = validated_names.split('\n')
    extracted_names = []
    for line in lines:
        match = re.match(r'^\d+\.\s(.+)$', line.strip())
        if match:
            company_name = match.group(1).strip()
            extracted_names.append(company_name)
    return extracted_names

def LinkedinSearch(extracted_names):

    linkedin=[]
    for company_name in extracted_names:
        query = f"{company_name} Company Linkedin ID"
        results = search.results(query)
        links = [result['link'] for result in results['organic']]
        linkedin.append(links[0])
        
    return linkedin



def categorize_information(info_list):
    info_dict = {
        'website': '',
        'industry': '',
        'employee_size': '',
        'associated_members': '',
        'location': '',
        'founded': '',
        'additional_info': []
    }
    
    for info in info_list:
        if info.startswith('http'):
            info_dict['website'] = info
        elif re.match(r'^\d{4}$', info): 
            info_dict['founded'] = info
        elif 'employees' in info:
            info_dict['employee_size'] = info
        elif 'LinkedIn members who’ve listed' in info:
            info_dict['associated_members'] = info
        elif 'associated members' in info:
            info_dict['associated_members'] = info
        elif re.match(r'^[A-Za-z\s]+,\s[A-Za-z\s]+$', info): 
            info_dict['location'] = info
        elif 'employees' not in info and re.match(r'^[A-Za-z\s,]+$', info):
            if info_dict['industry'] == '':
                info_dict['industry'] = info
            else:
                info_dict['additional_info'].append(info)
        else:
            info_dict['additional_info'].append(info)
            
    return info_dict

def clean_list(data_list):

    return [str(item) if item is not None else 'NA' for item in data_list]

def detect_sub_domain_and_categories(industry):
    categories_dict = {
        "retail": ["Grocery", "Food & Beverages", "Fashion", "Beauty & Personal Care", 
                   "Electronics", "Appliances", "Home & Kitchen", "Health & Wellness"],
        "tech": ["Electronics", "Software", "Hardware", "Gadgets"],
        "healthcare": ["Health & Wellness", "Medical Devices", "Pharmaceuticals"],
    }

    sub_domains_dict = {
        "retail": ["Consumer Packaged Goods (CPG)", "Fast Moving Consumer Goods (FMCG)", 
                   "Omnichannel", "Supermarkets", "D2C Brands", "Brand Aggregators", 
                   "Food & Beverages", "Restaurant Chains"],
        "tech": ["SaaS", "Cloud Computing", "Artificial Intelligence", "IoT"],
        "healthcare": ["Hospitals", "Clinics", "Pharmaceutical Companies", "Medical Research"],
    }

    categories = categories_dict.get(industry.lower(), [])

    sub_domains = sub_domains_dict.get(industry.lower(), [])
    
    return categories, sub_domains


def prompt_template(company_name, industry,about):
    categories, sub_domains = detect_sub_domain_and_categories( industry)

    prompt = f"""
    Company: {company_name}
    Industry: {industry}
    About Company:{about}
    
    Categories it should belong to:
    {', '.join(categories) if categories else 'No categories found'}
    
    Sub-Domains:
    {', '.join(sub_domains) if sub_domains else 'No sub-domains found'}

    Guidelines:
    - Return only categories and sub-domains

    Example:
    - Valid: "Food & Beverages", "Restaurant Chains"
    - Invalid: "Hospitals", "Fast Moving Consumer Goods (FMCG)" , 'SaaS'

    Categories:
    
    Sub-Domains:
    
    """
    messages = [
        {"role": "system", "content": "You are an AI bot that helps finding a categories and sub_domains of the company"},
        {"role": "user", "content": prompt}
    ]
    response_company = client.chat.completions.create(
        model="gpt4o_deployment",
        messages=messages,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    return response_company.choices[0].message.content
    
def sub_details(company_name,industry,about):

    response_text = prompt_template(company_name, industry, about)

    # Use regular expressions to extract categories and sub-domains from the response
    categories_pattern = re.compile(r'Categories:\n((?:- .+\n)+)')
    sub_domains_pattern = re.compile(r'Sub-Domains:\n((?:- .+\n)+)')

    categories_matches = categories_pattern.search(response_text)
    sub_domains_matches = sub_domains_pattern.search(response_text)

    if categories_matches:
        categories = [match.strip() for match in categories_matches.group(1).strip().split('\n') if match.startswith('-')]
        categories = [category[2:].strip() for category in categories]  # Remove leading '- '
    else:
        categories = []

    if sub_domains_matches:
        sub_domains = [match.strip() for match in sub_domains_matches.group(1).strip().split('\n') if match.startswith('-')]
        sub_domains = [sub_domain[2:].strip() for sub_domain in sub_domains]  # Remove leading '- '
    else:
        sub_domains = []

    if  categories and sub_domains:
        return categories,sub_domains
    else:
        response_text = prompt_template(company_name, industry, about)

        # Use regular expressions to extract categories and sub-domains from the response
        categories_pattern = re.compile(r'Categories:\n((?:- .+\n)+)')
        sub_domains_pattern = re.compile(r'Sub-Domains:\n((?:- .+\n)+)')

        categories_matches = categories_pattern.search(response_text)
        sub_domains_matches = sub_domains_pattern.search(response_text)

        if categories_matches:
            categories = [match.strip() for match in categories_matches.group(1).strip().split('\n') if match.startswith('-')]
            categories = [category[2:].strip() for category in categories]  # Remove leading '- '
        else:
            categories = []

        if sub_domains_matches:
            sub_domains = [match.strip() for match in sub_domains_matches.group(1).strip().split('\n') if match.startswith('-')]
            sub_domains = [sub_domain[2:].strip() for sub_domain in sub_domains]  # Remove leading '- '
        else:
            sub_domains = []
        return categories,sub_domains



def get_annual_revenue(snippets):


    prompt_template=f"""

    Text:
    {snippets}

    ### Task:
    Identifying Annual Revenue from Given article Text using recent date

    Guidelines:

    - Give Only the Annual Revenue In INR.
    - Annual Revenue should be Recent date.
    - If Annual Revenue is not available Generate the Annual Revenue of the company for the recent fiscal year.
    - Give only Annual Revenue.

    Annual Revenue:

    """

    messages = [
        {"role": "system", "content": "You are an AI bot that helps for Finding Annual Revenue of the company"},
        {"role": "user", "content": prompt_template}
    ]
    response_company = client.chat.completions.create(
        model="gpt4o_deployment",
        messages=messages,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    return response_company.choices[0].message.content

def annual_revenue_article(company_name):
    query = f"Provide the latest annual revenue of {company_name} in INR. Also, mention the fiscal year for which this revenue is reported."

    # Fetch search results from Google Serper API
    results = search.results(query)

    # Extract links and snippets from organic search results
    snippets = ""
    for result in results['organic']:
        snippets += result['snippet']
        if 'date' in result and result['date']:
            snippets += " " + result['date']
    result_revenue=get_annual_revenue(snippets)
    return result_revenue


def function_call_llm(designation_details):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "format_json",
                "description": "Format the data into the specified JSON structure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "designation_details": {
                            "type": "array",
                            "description": "A list containing names, positions, and LinkedIn URLs",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Name of the individual"},
                                    "position": {"type": "string", "description": "Executive-level position held by the individual"},
                                    "linkedin_url": {"type": "string", "description": "LinkedIn profile URL of the individual"}
                                },
                                "required": ["name", "position", "linkedin_url"]
                            }
                        }
                    },
                    "required": ["designation_details"]
                }
            }
        }
    ]

    messages = [
        {"role": "system", "content": "You are an intelligent AI bot that helps in formatting the data into the specified JSON structure."},
        {"role": "user", "content": f"Format the data into JSON.\n {designation_details}"}
    ]

    response = client.chat.completions.create(
        model="gpt4o_deployment",
        messages=messages,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        tools=tools
    )
    
    # Return the LLM's response
    return response.choices[0].message

def extract_persona(user_input):
    messages = [
        {"role": "system", "content": "You are an Intelliegent AI bot that helps in extracting specific executive-level information from a list of names, positions, and LinkedIn URLs."},
        {"role": "user", "content": f"""

### Task :
    - Given the following list of names, positions, and LinkedIn URLs, extract the details (name, position, LinkedIn URL) for individuals holding related positions listed under the headlines .
         
### Position:
- Chief Executive Officer, CEO
- Chief Operating Officer, COO
- Chief Technology Officer, CTO
- Chief Financial Officer, CFO
- Chief Strategy Officer, CSO
- Chief Compliance Officer, CCO
- Chief Growth Officer, CGO
- Chief Marketing Officer, CMO
- Chief Revenue Officer, CRO
- Chief Commercial Officer, CCO
- Chief Administrative Officer, CAO
- Chief Investment Officer, CIO
- Chief Risk Officer, CRO
- President
- Managing Director, MD
- Executive Vice President, EVP
- Senior Vice President, SVP
- Vice President, VP
- Director
- National Sales Manager
- VP Partnerships
- Executive Director
- Managing Director & CEO
- Head of Business
- Business Development
- Head of Sales
- Head of Marketing
- Head of Engineering
- Head of Product
- Head of Operations
- Head of Strategy
- Head of Corporate Development
- Head of Technology
- Head of Finance
- Head of Customer Success
- General Manager, GM
- Regional Director
- National Director
- Area Manager
- Senior Manager
- Lead Manager
- Senior Consultant
- Principal Consultant
- Principal
- Partner
- Product Manager
- Associate Partner
- Managing Partner
- Executive Partner
- Strategic Partner
- Head of Innovation
- Head of Product Strategy
- Head of Product Development
- Director of Product Management
- Director of Engineering
- Director of Sales
- Director of Marketing
- Director of Operations
- Director of Strategy
- Director of Finance
- Director of Business Development
- Director of Customer Success
- Director of Technology
- Director of Corporate Development
- Senior Vice President of Sales
- Senior Vice President of Marketing
- Senior Vice President of Engineering
- Senior Vice President of Product
- Senior Vice President of Operations
- Senior Vice President of Strategy
- Chief Risk Officer, CRO
- Chief Investment Officer , CIO
- Chief Credit Officer , CCO
- Chief Underwriting Officer , CUO
- Chief Distribution Officer , CDO
- Head of Credit Risk
- Vice President (VP) - Credit, VP - Credit
- Senior Credit Manager
- Director of Credit Underwriting
- Head of Risk Management
- Senior Vice President (SVP) - Risk & Compliance, SVP - Risk & Compliance
- Credit Risk Officer
- Head of Personal Loans
- Vice President (VP) - Personal Finance, VP - Personal Finance
- Director of Consumer Lending
- Head of Unsecured Lending
- Vice President (VP) - Small Business Finance, VP - Small Business Finance
- Director of SME Lending
- Senior Manager - Business Loans
- Head of Microfinance
- Head of Sales - Business Loans
- Head of Insurance
- Head of Underwriting
- Vice President (VP) - Underwriting, VP - Underwriting
- Director of Underwriting
- Vice President (VP) - Insurance Products, VP - Insurance Products
- Director of Insurance Operations
- Senior Underwriter
- Insurance Product Manager
- Head of Investments
- Vice President (VP) - Investments, VP - Investments
- Portfolio Manager
- Investment Strategist
- Director of Asset Management
- Senior Analyst - Investments
- Head of Wealth Management
- Vice President (VP) - Digital Transformation, VP - Digital Transformation
- Head of Sales - Insurance
- Vice President (VP) - Sales & Distribution, VP - Sales & Distribution
- Director of Agency Development
- Senior Manager - Sales Operations
- Head of Bancassurance
- Vice President (VP) - Channel Development, VP - Channel Development
- Head of Broker Relations
- Director of Investment Strategy
- Head of Asset Allocation
- Director of Channel Development
- Head of Distribution Partnerships
- Head of Wealth Management Sales
     
### Input :{user_input}

### GuideLines:

- Provide only the JSON output without any additional text.

### Include similar positions. For example:
- 'Chief Executive Officer' and 'CEO'
- 'Chief Operations Officer' and 'COO'
- 'Vice President' and 'VP'
- 'Managing Director & CEO' and 'MD & CEO'
- 'President' and 'president - retail Business'
- 'Project and Product Manager' - 'Project' and 'Product Manager'


### sample Output Format
The output should list only those individuals who hold the specified positions or similar positions or related positions, in the following format:

[
  {{"name": "Name X", "position": "Position X", "linkedin_url": "URL X"}},
  {{"name": "Name Y", "position": "Position Y", "linkedin_url": "URL Y"}},
  ...
]


"""}]

    response = client.chat.completions.create(
        model="gpt4o_deployment",
        messages=messages,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    all_designation_details=[]
    name=[]
    position=[]
    linkedin=[]
    try:
        result = response.choices[0].message.content
        clean_result=result.replace('```','')
        clean_result=clean_result.replace('json','')
        print(result)
        try :
            fun_result=function_call_llm(clean_result)
            args=json.loads(fun_result.tool_calls[0].function.arguments)
            print("argfs",args['designation_details'])
            result_data=args['designation_details']
        except Exception as e:
            result_data=json.loads(clean_result)
            print("Error")
    except Exception as e:
        print("Error in Headline",e)
    try:
        for person in result_data:
            name.append(person['name'])
            position.append(person['position'])
            linkedin.append(person['linkedin_url'])
    except Exception as e:
        print("No json is created")
    return name,position,linkedin


def get_persona(input_data):
    titles = ["Chief Executive Officer", "CEO", "Chief Operating Officer", "COO", 
          "Chief Financial Officer", "CFO", "Chief Strategy Officer", "CSO", 
          "Chief Compliance Officer", "CCO", "Chief Growth Officer", "CGO", 
          "President", "Managing Director", "MD", "Executive Vice President", "EVP", 
          "Senior Vice President", "SVP", "Product Management", "Chief Product Officer", 
          "CPO", "Vice President of Product Management", "Director of Product Management", 
          "Head of Product", "Senior Product Manager", "Product Manager", 
          "Associate Product Manager", "Product Owner", "Group Product Manager", 
          "Principal Product Manager", "Chief Technology Officer", "CTO", 
          "Chief Information Officer", "CIO", "Vice President of Engineering", 
          "Director of Engineering", "Head of Engineering", "Senior Software Engineer", 
          "Engineering Manager", "Chief Digital Officer", "CDO", "IT Director", 
          "Lead Developer", "Chief Sales Officer", "CSO", "Vice President of Sales", 
          "Director of Sales", "Head of Sales", "National Sales Manager", 
          "Regional Sales Manager", "Sales Manager", "Senior Account Executive", 
          "Key Account Manager", "Business Development Manager", "Chief Marketing Officer", 
          "CMO", "Vice President of Marketing", "Director of Marketing", "Head of Marketing", 
          "Marketing Manager", "Brand Manager", "Digital Marketing Manager", 
          "Content Marketing Manager", "Growth Marketing Manager", "Marketing Analyst", 
          "Chief Business Officer", "CBO", "General Manager", "GM", "Chief Administrative Officer", 
          "CAO", "Chief Revenue Officer", "CRO", "Chief Corporate Development Officer", "CCDO", 
          "Vice President of Operations", "Director of Operations", "Head of Business Development", 
          "Senior Operations Manager", "Corporate Vice President", "CVP", 
          "Chief Business Development Officer", "CBDO", "Deputy Managing Director", "DMD", 
          "Chief Investment Officer", "CIO", "Chief Risk Officer", "CRO", 
          "Executive Director", "ED", "Head of Corporate Strategy", 
          "Vice President of Corporate Affairs", "Director of Corporate Development", 
          "Principal of Operations", "Associate Vice President", "AVP", 
          "Head of Product Innovation", "Product Strategy Manager", 
          "Director of Product Strategy", "Senior Product Director", 
          "Chief Product Development Officer", "CPDO", "Vice President of Product Development", 
          "Director of Product Development", "Lead Product Manager", "Principal Product Owner", 
          "Product Portfolio Manager", "Vice President of Product Design", 
          "Director of Product Design", "Senior Product Owner", "Product Lifecycle Manager", 
          "Product Line Manager", "Product Development Manager", "Product Innovation Manager", 
          "Group Product Owner", "Head of Product Management", "Principal Product Designer", 
          "Head of Business Development", "Sales Director", "Vice President of Business Development", 
          "Director of Business Development", "Senior Sales Director", 
          "Chief Commercial Officer", "CCO", "Vice President of Commercial Operations", 
          "Director of Commercial Operations", "Head of Commercial Operations", 
          "Senior Commercial Manager", "Sales Operations Director", 
          "Vice President of Sales Operations", "Director of Sales Operations", 
          "Head of Sales Operations", "Senior Sales Operations Manager", 
          "Strategic Account Manager", "National Account Manager", "Director of Key Accounts", 
          "Senior Key Account Manager", "Regional Account Manager", "Sales", 
          "Director", "Product", "Chief", "Officer", "Vice President", "Head", "Manager", 
          "Operations", "Development", "Marketing", "Account", "Strategy", "Compliance", 
          "Corporate", "Executive", "President", "Growth", "Business",
          "Chief Risk Officer", "CRO","Chief Investment Officer", "CIO","Chief Credit Officer", "CCO",
          "Chief Underwriting Officer", "CUO","Chief Distribution Officer", "CDO",
          "Head of Credit Risk","Vice President (VP) - Credit", "VP - Credit","Senior Credit Manager","Director of Credit Underwriting", 
          "Head of Risk Management", "Senior Vice President (SVP) - Risk & Compliance", "SVP - Risk & Compliance",
          "Credit Risk Officer", "Head of Personal Loans", "Vice President (VP) - Personal Finance", "VP - Personal Finance",
          "Director of Consumer Lending", "Head of Unsecured Lending","Vice President (VP) - Small Business Finance", "VP - Small Business Finance",
          "Director of SME Lending", "Senior Manager - Business Loans","Head of Microfinance", "Head of Sales - Business Loans", 
          "Head of Insurance", "Head of Underwriting", "Vice President (VP) - Underwriting", "VP - Underwriting","Director of Underwriting", 
          "Vice President (VP) - Insurance Products", "VP - Insurance Products","Director of Insurance Operations", "Senior Underwriter",
          "Insurance Product Manager","Head of Investments","Vice President (VP) - Investments", "VP - Investments",
          "Portfolio Manager", "Investment Strategist", "Director of Asset Management", "Senior Analyst - Investments",
          "Head of Wealth Management","Vice President (VP) - Digital Transformation", "VP - Digital Transformation",
          "Head of Sales - Insurance", "Vice President (VP) - Sales & Distribution", "VP - Sales & Distribution",
          "Director of Agency Development", "Senior Manager - Sales Operations", "Head of Bancassurance", "Vice President (VP) - Channel Development", 
          "VP - Channel Development","Head of Broker Relations","Director of Investment Strategy","Head of Asset Allocation",
          "Director of Channel Development", "Head of Distribution Partnerships","Head of Wealth Management Sales"]

    # Create a regex pattern for the titles
    pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, titles)) + r')\b', re.IGNORECASE)

    filtered_names = []
    filtered_positions = []
    filtered_linkedin_urls = []
    non_filtered_names = []
    non_filtered_positions = []
    non_filtered_linkedin_urls = []

    # Filter the list based on the pattern and store the results
    for person in input_data:
        if pattern.search(person['position']):
            filtered_names.append(person['name'])
            filtered_positions.append(person['position'])
            filtered_linkedin_urls.append(person['linkedin_url'])
        else:
            non_filtered_names.append(person['name'])
            non_filtered_positions.append(person['position'])
            non_filtered_linkedin_urls.append(person['linkedin_url'])
    
    print("Filtered Results:")
    print(filtered_names, filtered_positions, filtered_linkedin_urls)
    
    print("\nNon-Filtered Results:")
    print(non_filtered_names, non_filtered_positions, non_filtered_linkedin_urls)
    
    return (filtered_names, filtered_positions, filtered_linkedin_urls), (non_filtered_names, non_filtered_positions, non_filtered_linkedin_urls)


def split_data(data_list, num_splits):
    """Split the data_list into num_splits parts."""
    avg_len = len(data_list) // num_splits
    remainder = len(data_list) % num_splits
    splits = []
    start = 0
    
    for i in range(num_splits):
        end = start + avg_len + (1 if i < remainder else 0)
        splits.append(data_list[start:end])
        start = end
    return splits

def process_and_combine_results(data_list, num_splits):
    """Split the data_list if necessary, process each split with extraction_func, and combine unique results."""
    if len(data_list) <= num_splits:
        # If data size is less than or equal to number of splits, process as a single batch
        splits = [data_list]
    else:
        # Split data into parts
        splits = split_data(data_list, num_splits)
    
    nameing = []
    positioning = []
    linked_urls = []
    results=[]
    # Process each split
    for split in splits:
        name,position,linkedin_url=extract_persona(split)  
        nameing.extend(name)
        positioning.extend(position)
        linked_urls.extend(linkedin_url)


    return nameing,positioning,linked_urls



def extract_details(url):

    service = Service('/usr/local/bin/chromedriver')

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-zygote')
    # Login 
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("Yes ")
    driver.get('https://www.linkedin.com/login')
    time.sleep(2) 
    print("Yes2")
    username_field = driver.find_element(By.ID, 'username')
    username_field.send_keys('barathraj.p2022ai-ds@sece.ac.in')
    password_field = driver.find_element(By.ID, 'password')
    password_field.send_keys('sece.ac.in')
    password_field.send_keys(Keys.RETURN)
    time.sleep(3) 
    
    # About page:
    home_page_url = str(url) + '/about'
    print("Home page")
    driver.get(home_page_url)
    
    # Title
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'org-top-card-summary__title')))
        company_name = driver.find_element(By.CLASS_NAME, 'org-top-card-summary__title').text
    except:
        company_name = ""
    
    # Overview
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'p')))
        about = driver.find_elements(By.TAG_NAME, 'p')[1].text  
    except:
        about = ""
    
    # Details
    detail = []
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'dd')))
        details = driver.find_elements(By.TAG_NAME, 'dd')
        for det in details:
            detail.append(det.text)
        clean_details = categorize_information(detail)
    except:
        clean_details = {
            'website': "",
            'industry': "",
            'employee_size': "",
            'location': "",
            'founded': "",
            'additional_info': ""
        }

    people_url = str(url) + '/people'
    driver.get(people_url)
    
    print("People Page",people_url)
    keywords = ['ceo','president', 'director', 
             'head', 'manager', 'development', 
            'operations', 'sales', 'marketing', 'business',
            'product', 'Technology']
    results_persona = []

    # Iterate over each keyword and collect designations
    for keyword in keywords:
        # Generate the URL for each keyword
        people_u = people_url + f'/?keywords={keyword}'
        print(f"People URL: {people_u}")
        driver.get(people_u)

        
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'org-people-profile-card__profile-title')))
        except:
            print(f"Failed to load page for title: {people_u}")
            continue  # Move to the next keyword if the page fails to load
        
        SCROLL_PAUSE_TIME = 4

        # Check and click "Show more results" button until it no longer appears
        while True:
            try:
                show_more_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'artdeco-button__text') and contains(text(), 'Show more results')]"))
                )
                if show_more_button:
                    show_more_button.click()
                    time.sleep(3)  # Pause for loading new content
                else:
                    break
            except:
                break  # Exit the loop if no "Show more results" button is found
        
        # Scroll until the bottom of the page is reached
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Collect LinkedIn profile URLs
        i = 0
        linked_url = []
        while True:
            lnks = driver.find_elements(By.ID, f"org-people-profile-card__profile-image-{i}")
            if not lnks:
                break
            for lnk in lnks:
                linked_url.append(lnk.get_attribute('href'))
            i += 1

        # Collect Titles (Designations)
        titles_list = []
        try:
            title_elements = driver.find_elements(By.CLASS_NAME, 'lt-line-clamp--single-line')
            for tit in title_elements:
                titles_list.append(tit.text)
        except:
            titles_list = []

        # Collect Headlines (Summaries/Headlines)
        headline = []
        try:
            head_elements = driver.find_elements(By.CLASS_NAME, 'lt-line-clamp--multi-line')
            for i, hea in enumerate(head_elements):
                if i % 2 == 0:
                    headline.append(hea.text)
            clean_headline = clean_list(headline)
        except:
            clean_headline = []

        url_link = clean_list(linked_url)

        # Store collected data
        persona = [{'name': n, 'position': h, 'linkedin_url': u} for n, h, u in zip(titles_list, clean_headline, url_link)]
        
        for person in persona:
            results_persona.append({
                'name': person['name'],
                'position': person['position'],
                'linkedin_url': person['linkedin_url']
            })

    print("Total Length of Persona",len(results_persona))

    unique_entries = {frozenset(item.items()): item for item in results_persona}.values()

    # Convert the unique_entries back to a list
    final_results = list(unique_entries)

    filterd,non_filterd=get_persona(final_results)
    nameing,positioning,linkedin_urling=filterd
    data_list=[{'name': n1, 'position': h1, 'linkedin_url': u1} for n1, h1, u1 in zip(nameing, positioning, linkedin_urling)]

    total_name,total_poition,total_url=process_and_combine_results(data_list,5)
    print("final len of names",len(total_name))

    categories,sub_domains=sub_details(company_name,clean_details['industry'],about)
    annual_revenue = annual_revenue_article(company_name)
    
    data = {
        'Company_name': company_name,
        'about': about,
        'categories':categories,
        'sub_domains':sub_domains,
        'website': clean_details['website'],
        'industry': clean_details['industry'],
        'employee_size': clean_details['employee_size'],
        'annual_revenue':annual_revenue,
        'location': clean_details['location'],
        'founded': clean_details['founded'],
        'additional_info': clean_details['additional_info'],
        'people_name': total_name,
        'headline':total_poition,
        'linked_url': total_url
    }
    
    driver.quit()
    return data


def get_company_name_industry(domain): 
    queries = [
        f'site:.com OR site:.org OR site:.net "{domain} Companies in India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales" OR loc:"India") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")'
        #f'site:.com OR site:.org OR site:.net "Top {domain} Companies in India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")',
        # f'site:.com OR site:.org OR site:.net "Leading {domain} Companies in India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")',
        # f'site:.com OR site:.org OR site:.net "{domain} Industry in India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")',
        # f'site:.com OR site:.org OR site:.net "{domain} Sector in India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")',
        # f'site:.com OR site:.org OR site:.net "Major {domain} Companies in India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")',
        # f'site:.com OR site:.org OR site:.net "Best {domain} Companies in India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")',
        # f'site:.com OR site:.org OR site:.net source:"{domain}Companiesinindia" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")',
        # f'site:.com OR site:.org OR site:.net intitle:"{domain} Industry Companies" loc:"India" AND ("store" OR "shop" OR "outlet" OR "consumer products" OR "sales") -("technology" OR "automobile" OR "telecom" OR "pharmaceutical" OR "Financial" OR "Manufacturer")'
    ]
    all_links = []
    for query in queries:
        try:
            results = search.results(query)
            links = [entry['link'] for entry in results['organic']]
            all_links.extend(links)
        except Exception as e:
            print(f"Error during search: {e}")
    
    print(f"Total links found: {len(all_links)}")

    company_names = []
    if all_links:
        try:
            for link in all_links:  # Process only the first link
                content = scrape_content(link)
                if content:
                    print(f"Scraped content from {link[:50]}...")  # Debug: Show part of the scraped content
                    cleaned_text = clean_text(content)
                    chunks = split_text_into_chunks(cleaned_text, 1000)
                    for chunk in chunks:
                        try:
                            names = extract_company_names(chunk)
                            print(f"Extracted names chunk: {chunk[:50]}...")  # Debug: Show part of the chunk
                            if names.tool_calls and names.tool_calls[0].function.arguments:
                                args = json.loads(names.tool_calls[0].function.arguments)
                                if 'list_of_company_names' in args:
                                    company_names.extend(args['list_of_company_names'])
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"Error parsing JSON or accessing keys: {e}")
        except Exception as e:
            print(f"Error processing content from {link}: {e}")
    
    if not company_names:
        print("No company names were extracted.")
    
    linked = []
    extracted_names = []
    try:
        if company_names:
            validated_names = validate_company_names(company_names)
            extracted_names = clean_extracted_name(validated_names)
            linked = LinkedinSearch(extracted_names)
            linked_updated = [url.replace('in.linkedin.com', 'www.linkedin.com') for url in linked]
        else:
            print("Company names list is empty.")
            linked_updated = []
    except Exception as e:
        print(f"Error during LinkedIn search: {e}")
        linked_updated = []

    print(f"Final extracted names: {extracted_names}") 
    print(f"Final LinkedIn URLs: {linked_updated}")  
    # extracted_names=['titan','google']
    # linked_updated=['https://www.linkedin.com/company/celikon-impex-pvt-ltd','https://www.linkedin.com/company/adyaondc']
    return extracted_names, linked_updated

@app.context_processor
def utility_processor():
    return dict(enumerate=enumerate)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    industry = request.form['industry']
    csv_file = '/home/ubuntu/lead_gen_tool/retail.csv'  
    data = read_csv(csv_file)
    return render_template('index.html', companies=data)

def read_csv(file_path):
    df = pd.read_csv(file_path)
    return df.to_dict(orient='records')

@app.route('/company/<int:index>/<industry>')
def company_detail(index, industry):
    csv_file = '/home/ubuntu/lead_gen_tool/retail.csv'
    data = read_csv(csv_file)
    company = data[index]
    
    # Printing company name
    print("Company_name", company['headline'])

    company_headline_list = ast.literal_eval(company['headline'])

    name = company['people_name'].strip("[]").replace("'", "").split(',')
    linkedin = company['linked_url'].strip("[]").replace("'", "").split(',')
    emails = company['email'].strip("[]").replace("'", "").split(',')  # Add emails

    # Clean up the lists
    name = [n.strip() for n in name]
    linkedin = [l.strip() for l in linkedin]
    emails = [e.strip() for e in emails]  # Clean emails

    # Combine the lists into a 'workers' dictionary
    company['workers'] = [{'name': n, 'headline': h, 'linkedin_url': u, 'email': e} 
                          for n, h, u, e in zip(name, company_headline_list, linkedin, emails)]
    
    print(company)
    return render_template('company_detail.html', company=company, industry=industry)

@app.route('/gen_main')
def gen_main():
    return render_template('gen_main.html')

@app.route('/company_gen')
def company_gen():
    return render_template('company_gen.html')
company_session=[]
existing_names = []
existing_linkedin = []

@app.route('/company_name/submit', methods=['POST'])
def handle_submit():
    csv_file = '/home/ubuntu/lead_gen_tool/retail.csv'
    df = pd.read_csv(csv_file)

    selected_industry = request.form.get('gen_radio')
    company_name, linkedin_url = get_company_name_industry(selected_industry)
    for name, link in zip(company_name, linkedin_url):
        # Check if the name exists in the DataFrame
        if name in df['Company_name'].values:
            similar_names = df[df['Company_name'].str.contains(name, case=False, na=False)]
            for sim_name in similar_names['Company_name']:
                if sim_name == name:
                    existing_names.append(name)
                    existing_linkedin.append(link)
                elif link == '' and sim_name == name:
                    existing_names.append(name)
                    existing_linkedin.append(link)
    
    unique_names = [name for name in company_name if name not in existing_names]
    unique_linkedin = [link for name, link in zip(company_name, linkedin_url) if name not in existing_names]
    companies = [{'name': c, 'linkedin_url': l} for c, l in zip(unique_names, unique_linkedin) if l]
    company_session.append(companies)   
    return render_template('company_gen.html', companies=companies)

@app.route('/submit_selection', methods=['POST'])
def submit_selection():
    selected_companies = request.form.getlist('selected_companies')
    print(selected_companies)
    result_company=[]
    for select in selected_companies:
        splited_company=select.split('|')
        result_company.append(splited_company[1])
    company=[]
    for i in result_company:
        try:
            print("value",i)
            data = extract_details(str(i))
            company.append(data)
                
        except Exception as e:
            print("Error")

    return render_template('gen_main.html', selected_companies=company)


@app.route('/submit_all', methods=['POST'])
def submit_all():
    company=[]
    print("company_sesion",company_session)
    selected_companies = company_session[0]
    print("Selected Company Details",selected_companies)
    for lin in selected_companies:
        try:
            data = extract_details(lin['linkedin_url'])
            company.append(data)    
        except Exception as e:
            print("Error")
    return render_template('gen_main.html',selected_companies=company)

@app.route('/duplicate')
def duplicate():
    try:
        companies = [{'name': c, 'linkedin_url': l} for c,l in zip(existing_names, existing_linkedin)]
    except Exception as e:
        print("No Duplicates")
    return render_template('duplicate.html',companies=companies)

@app.route('/Duplicate_extraction', methods=['POST'])
def duplicate_extraction():
    selected_companies = request.form.getlist('Duplicate_company')
    result_company = []
    for select in selected_companies:
        splited_company = select.split('|')
        result_company.append(splited_company[1])
    
    company = []
    for i in result_company:
        try:
            data = extract_details(i)
            company.append(data)  
            print("company",company)  
        except Exception as e:
            print("Error", e)
    df_new = pd.DataFrame(company)
    df_existing = pd.read_csv('/home/ubuntu/lead_gen_tool/retail.csv')
    if set(df_new.columns) != set(df_existing.columns):
        raise ValueError("The columns of the new data do not match the existing data")
    df_existing.set_index('Company_name', inplace=True)
    df_new.set_index('Company_name', inplace=True)

    df_existing.update(df_new)

    df_combined = df_existing.combine_first(df_new)

    df_combined.reset_index(inplace=True)

    df_combined.to_csv('/home/ubuntu/lead_gen_tool/retail.csv', index=False)

    return render_template('index.html')

@app.route('/handle_text_submit', methods=['POST'])
def handle_text_submit():
    csv_file='/home/ubuntu/lead_gen_tool/retail.csv'
    df=pd.read_csv(csv_file)
    user_input = request.form['user_input']
    domain_filter = user_input.split(',')
    
    unique_companies = {}
    print("Domain_filter",domain_filter)
    for dom in domain_filter:
        dom=str(dom).lower()
        print(dom)
        com_name, com_linkedin_id = get_company_name_industry(dom)
        
        for com_n, com_i in zip(com_name, com_linkedin_id):
            unique_companies[com_n] = com_i
    
    filter_name = list(unique_companies.keys())
    filter_id = list(unique_companies.values())
    existing_filter_names=[]
    existing_filter_linkedin=[]

    for na,li in zip(filter_name,filter_id):

        if na in df['Company_name'].values:
            existing_filter_names.append(na)
            existing_filter_linkedin.append(li)

    unique_names = [name for name in filter_name if name not in existing_filter_names]
    unique_linkedin = [link for link in filter_id if link not in existing_filter_linkedin]
    companies = [{'name': c, 'linkedin_url': l} for c,l in zip(unique_names, unique_linkedin)]
    company_session.append(companies)

    return render_template('company_gen.html', companies=companies)

import logging

def fetch_linkedin_data(linkedin_url):
    print("Entering the function to collect emails for URL2:", linkedin_url)
    try:
        # Lookup LinkedIn data using RocketReach API (assuming lookup_result is the response)
        if result_rocket_reach.is_success:
            print("Yes")
            lookup_result = rr.person.lookup(linkedin_url=linkedin_url)
            print("Lookup result for URL", linkedin_url, ":", lookup_result)
            
            if lookup_result.is_success:
                print("yes2")
                data_str = repr(lookup_result.person)
                result = ast.literal_eval(data_str)
                # Extract email and phone from the result
                email_data = result.get('current_work_email', "")

                if not email_data:  # If current_work_email is not available, fallback to emails list
                    emails = result.get('emails', [])
                    if emails:
                        email_data = emails[0].get('email', "")
                
                # Handling phone extraction
                listing = result.get('phones', [])
                if listing and isinstance(listing, list):
                    phone_num = listing[0].get('number', "")
                else:
                    phone_num = ""

                return email_data, phone_num

            else:
                print(f"No data returned for URL: {linkedin_url}")
                return "", ""
        else:
            return "",""
    except:
        logging.error(f"Error occurred during LinkedIn data fetch for URL {linkedin_url}")
        return "", ""

@app.route('/update', methods=['POST'])
def update():
    selected_industry = request.form.getlist('selected_companies_details')
    print("Selected Companies", selected_industry)
    
    for select in selected_industry:
        splited_company = select.split('#bar#')
        print("Split Company Details", splited_company)

        # Get the current date in dd/mm/yyyy format
        current_date = datetime.now().strftime('%d/%m/%Y')
        
        # Assuming LinkedIn URLs are stored in splited_company[13] as a JSON-like string
        linked_urls_str = splited_company[13]
        
        try:
            linkedin_urls = ast.literal_eval(linked_urls_str)  # Convert string representation of list to actual list
            if not isinstance(linkedin_urls, list):
                raise ValueError('LinkedIn URLs is not a valid list.')
        except (ValueError, SyntaxError) as e:
            print(f"Error parsing LinkedIn URLs: {e}")
            # Fallback: if parsing fails, treat the string as a simple comma-separated list
            linkedin_urls = linked_urls_str.split(',')
        
        linkedin_urls = [url.strip() for url in linkedin_urls if url.strip()]  # Clean and remove empty URLs
        print("LinkedIn URLs", linkedin_urls)

        emails = []
        phone_numbers = []
        larger=False
        if len(linkedin_urls) > 15:
            filterd_linkedin=linkedin_urls[:15]
            larger=True
        else:
            filterd_linkedin=linkedin_urls
        for linkedin_url in filterd_linkedin:
            print(f"Processing LinkedIn URL: {linkedin_url}")
            try:
                email, phone_num = fetch_linkedin_data(linkedin_url)
                time.sleep(20)
                emails.append(email)
                phone_numbers.append(phone_num)

            except Exception as e:
                logging.error(f"Error processing LinkedIn URL {linkedin_url}: {e}")
                continue  # Continue to next LinkedIn URL on error
        if larger:
            larger_linkedin=linkedin_urls[15:]
            for lin in larger_linkedin:
                emails.append("")
                phone_numbers.append("")

        company_data = {
            'Company_name': splited_company[0],
            'about': splited_company[1],
            'categories': splited_company[2],
            'sub_domains': splited_company[3],
            'website': splited_company[4],
            'industry': splited_company[5],
            'employee_size': splited_company[6],
            'annual_revenue': splited_company[7],
            'location': splited_company[8],
            'founded': splited_company[9],
            'additional_info': splited_company[10],
            'people_name': splited_company[11],
            'headline': splited_company[12],
            'linked_urls': linkedin_urls,
            'emails': emails,
            'contact_numbers': phone_numbers,
            'date': current_date
        }

        print("Company Data:", company_data)

        # Create DataFrame and append data to CSV
        df = pd.DataFrame([company_data])
        df.to_csv('/home/ubuntu/lead_gen_tool/retail.csv', mode='a', index=False, header=False)

    print("Data appended successfully.")
    return render_template('index.html')


def wrap_text(data):
    if pd.isna(data):
        return ''
    
    try:
        if isinstance(data, str):
            data = data.replace('"', '\\"').replace("'", '"')
            items = json.loads(data)
            if isinstance(items, list):
                return '\n'.join(items)
        return data 
    except (json.JSONDecodeError, TypeError):
        print(f"Error processing categories data: {data}")
        return data  

@app.route('/download')
def download():
    df = pd.read_csv('/home/ubuntu/lead_gen_tool/retail.csv')

    required_columns = ['Company_name', 'categories', 'sub_domains', 'website', 'industry', 'employee_size', 'annual_revenue', 'location', 'people_name', 'headline', 'linked_url', 'email', 'contact_number']

    if not all(column in df.columns for column in required_columns):
        raise ValueError(f"One or more required columns are missing from the CSV. Required columns are: {required_columns}")

    with open('/home/ubuntu/lead_gen_tool/output1.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        writer.writerow(['Company_name', 'categories', 'sub_domains', 'website', 'industry', 'employee_size', 'annual_revenue', 'location', 'people_name', 'headline', 'linked_url', 'email', 'contact_number', 'date'])

        for index, row in df.iterrows():
            # Company Name
            company_name = str(row['Company_name']).strip()
            # Categories
            categories = row['categories']
            formatted_categories = wrap_text(categories).strip()
            # Sub-domain
            sub_domain = row['sub_domains']
            formatted_sub_domain = wrap_text(sub_domain).strip()
            # Website
            website = str(row['website']).strip()
            # Industry
            industry = str(row['industry']).strip()
            # Employee size
            employee_size = str(row['employee_size']).strip()
            # Annual revenue
            annual_revenue = str(row['annual_revenue']).strip()
            # Location
            location = str(row['location']).strip()

            # Date
            date = str(row['date']).strip()

            # People name
            people_list = str(row['people_name'])
            try:
                people_splited = json.loads(people_list.replace("'", '"'))
            except json.JSONDecodeError:
                people_splited = people_list.split(',')

            # Headline
            clean_headline = str(row['headline'])
            try:
                headline_splited = json.loads(clean_headline.replace("'", '"'))
            except json.JSONDecodeError:
                try:
                    headline_splited = ast.literal_eval(clean_headline)
                except (ValueError, SyntaxError):
                    headline_splited = [clean_headline]

            # LinkedIn URL
            linkedin_ids_list = str(row['linked_url'])
            try:
                splited_link = json.loads(linkedin_ids_list.replace("'", '"'))
            except json.JSONDecodeError:
                splited_link = linkedin_ids_list.split(',')
            if not splited_link:
                splited_link = [''] * len(people_splited)

            # Email
            email_l=row['email']
            email_list = str(email_l).strip() if pd.notna(row['email']) else ''
            try:
                email_splited = json.loads(email_list.replace("'", '"'))
            except json.JSONDecodeError:
                email_splited = email_list.split(',')

            # Clean the emails: remove 'None', empty strings, and extra spaces/quotes
            
            if not email_splited:
                email_splited = [''] * len(people_splited)

            # Contact number
            contact_number_list = str(row['contact_number']).strip() if pd.notna(row['contact_number']) else ''
            try:
                contact_number_splited = json.loads(contact_number_list.replace("'", '"'))
            except json.JSONDecodeError:
                contact_number_splited = contact_number_list.split(',')
            if not contact_number_splited:
                contact_number_splited = [''] * len(people_splited)

            # Ensure that we match people, headlines, emails, and phone numbers correctly
            if len(headline_splited) < len(people_splited):
                headline_splited.extend(['NaN'] * (len(people_splited) - len(headline_splited)))

            if len(splited_link) < len(people_splited):
                splited_link.extend(['NaN'] * (len(people_splited) - len(splited_link)))

            if len(email_splited) < len(people_splited):
                email_splited.extend([''] * (len(people_splited) - len(email_splited)))

            if len(contact_number_splited) < len(people_splited):
                contact_number_splited.extend([''] * (len(people_splited) - len(contact_number_splited)))

            print("email",email_splited)
            print("Contact",contact_number_splited)

            # Now write the data for each person in the list
            for person, headline, linkedin_id, email, contact_number in zip(people_splited, headline_splited, splited_link, email_splited, contact_number_splited):
                writer.writerow([
                    company_name,
                    formatted_categories,
                    formatted_sub_domain,
                    website,
                    industry,
                    employee_size,
                    annual_revenue,
                    location,
                    person.strip(),
                    headline.strip(),
                    linkedin_id.strip(),
                    email.strip().replace('[','').replace(']','').replace('"',"").replace("'","").replace("None",""),
                    contact_number.strip(),
                    date
                ])

    return send_file('/home/ubuntu/lead_gen_tool/output1.csv', as_attachment=True)

@app.route('/get_contact_info', methods=['POST'])
def get_contact_info():
    data = request.get_json()
    linkedin_url = data.get('linkedin_url')

    if not linkedin_url:
        return jsonify({'status': 'error', 'message': 'LinkedIn URL is required'})
    
    sample_email,sample_phone=fetch_linkedin_data(linkedin_url)
    return jsonify({'status': 'success', 'email': sample_email, 'phone': sample_phone})

@app.route('/add_contact_info', methods=['POST'])
def add_contact_info():
    data = request.get_json()
    linkedin_url = data.get('linkedin_url')
    new_email = data.get('email')

    # Debugging print statements to check if we are getting the email and LinkedIn URL
    print(f"LinkedIn URL: {linkedin_url}")
    print(f"New Email: {new_email}")

    if not linkedin_url:
        return jsonify({'status': 'error', 'message': 'LinkedIn URL is required'})
    
    if not new_email:
        return jsonify({'status': 'error', 'message': 'Email is required'})

    # Read the CSV file
    df = pd.read_csv('/home/ubuntu/lead_gen_tool/retail.csv')

    # Flag to check if we found and updated the LinkedIn URL
    updated = False

    # Iterate through each row and check if LinkedIn URL is in the list of URLs
    for index, row in df.iterrows():
        try:
            # Convert both 'linked_url' and 'email' columns from strings to lists
            linked_urls = ast.literal_eval(row['linked_url'])
            emails = ast.literal_eval(row['email']) if pd.notna(row['email']) else [''] * len(linked_urls)

            # Find the specific LinkedIn URL in the list
            for i, url in enumerate(linked_urls):
                if linkedin_url.strip() == url.strip():  # Strict matching
                    # Check if the corresponding email is empty or update the existing email
                    if not emails[i]:  # If the email is empty
                        print(f"Current email is empty for LinkedIn URL: {linkedin_url}")
                    else:
                        print(f"Overwriting existing email for LinkedIn URL: {linkedin_url}")
                    
                    emails[i] = new_email  # Update the email at the same index
                    print(emails)
                    df.at[index, 'email'] = str(emails)  # Convert the list back to string for saving

                    updated = True
                    break  # Exit inner loop after updating

        except (ValueError, SyntaxError):
            continue  # Skip rows that are improperly formatted

        if updated:
            break  # Exit outer loop after updating the correct LinkedIn URL

    if updated:
        # Save the updated DataFrame back to the CSV file
        df.to_csv('/home/ubuntu/lead_gen_tool/retail.csv', index=False)
        return jsonify({'status': 'success', 'message': 'Email updated successfully!'})
    else:
        return jsonify({'status': 'error', 'message': 'LinkedIn URL not found'})

    
if __name__ == '__main__':
    app.run(host='0.0.0.0',port=8000)

