""" some functions for setting up the rag """

import sqlite3
import requests

import pdfplumber
from io import BytesIO

from datetime import datetime
from bs4 import BeautifulSoup
from haystack.components.generators import AzureOpenAIGenerator

def setup_database(db_name="test.sqlite"):
    """setup sqlite database and create table"""
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS '{db_name}' (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        url TEXT,
        keywords TEXT,
        date TEXT
    )
    """)
    conn.commit()
    cur.close()
    return conn


def get_link_list_zapf():
    """crawl ZaPF eV webpage"""
    url = "https://zapfev.de/zapf/resolutionen/"
    response = requests.get(url)
    assert response.status_code == 200

    soup = BeautifulSoup(response.content, 'html.parser')

    def convert_date_format(date: str) -> str:
        return datetime.strptime(date,  "%d.%m.%Y").strftime("%Y-%m-%d")

    link_list = [(row.find('a').get_text(), row.find('a')['href'], convert_date_format(row.find_all('td')[1].get_text())) 
                 if row.find('a') and len(row.find_all('td')) >= 2 else None 
                 for _, row in enumerate(soup.find_all('tr'))]
    return link_list


def get_link_list_jdpg(auth_data):
    """param: auth_data - (username, password) pair for access to the DPG web page"""
    s = requests.Session()
    response = s.get("https://www.dpg-physik.de/vereinigungen/fachuebergreifend/ak/akjdpg/jdpg-interner-bereich/uebersicht-aller-internen-dokumente", auth=auth_data)
    assert response.status_code == 200
    
    soup = BeautifulSoup(response.content, 'html.parser')

    def convert_date_format(date: str) -> str:
        return datetime.strptime(date,  "%d.%m.%Y %H:%M").strftime("%Y-%m-%d")

    link_list = [(
        row.find_all('a')[1].get_text(), 
        row.find_all('a')[1]["href"].replace("/view", ""), 
        convert_date_format(row.find_all('td')[2].get_text().strip())
        ) if row.find('a') and "Leitfaden" in row.find_all('a')[1].get_text() else None 
        for _, row in enumerate(soup.find_all('tr'))]
    return link_list


def get_keywords(generator: AzureOpenAIGenerator, text: str) -> str:
    generation_kwargs = {
        "temperature": 0
    }
    return generator.run(
        prompt=f"""Fasse den folgenden Text in mindestens 30 Schlagwörtern zusammen. 
        Bei Bedarf verwende thematisch passende Schlagwörter, auch wenn diese nicht unmittelbar im Text vorkommen.
        Gebe die Schlagwörter als kommagetrennte Liste aus.\n\n{text}""", generation_kwargs=generation_kwargs)["replies"][0]


def build_database(link_list, conn: sqlite3.Connection, generator: AzureOpenAIGenerator, base_url="", auth_data=None):
    cur = conn.cursor()
    for item in link_list:
        if item == None: 
            continue # no item to process
        print(item)
        (title, url, date) = item
        response = requests.get(base_url + url, auth=auth_data)
        assert response.status_code == 200

        pdf_text = ""
        pdf_file = BytesIO(response.content)
        with pdfplumber.open(pdf_file) as pdf:
            for _, page in enumerate(pdf.pages):
                pdf_text = pdf_text + page.extract_text() + "\n\n"

        cur.execute("""
    INSERT INTO documents (title, content, url, keywords, date)
    VALUES (?, ?, ?, ?, ?)
    """, (title, pdf_text, base_url + url, get_keywords(generator, pdf_text), date))
        conn.commit()
    cur.close()