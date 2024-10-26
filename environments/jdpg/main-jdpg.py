import sqlite3

import streamlit as st
import numpy as np
import pandas as pd

from haystack.components.generators import AzureOpenAIGenerator

generator = AzureOpenAIGenerator(
    azure_deployment="gpt-4o-mini", 
    azure_endpoint="https://ai-openai-swc-service.openai.azure.com/"
    )

def get_keywords(generator: AzureOpenAIGenerator, text: str) -> str:
    generation_kwargs = {
        "temperature": 0
    }
    return generator.run(
        prompt=f"""Fasse den folgenden Text in mindestens 30 Schlagwörtern zusammen. 
        Bei Bedarf verwende thematisch passende Schlagwörter, auch wenn diese nicht unmittelbar im Text vorkommen.
        Gebe die Schlagwörter als kommagetrennte Liste aus.\n\n{text}""", generation_kwargs=generation_kwargs)["replies"][0]

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

conn = setup_database(db_name="jdpg-leitfaden.sqlite")

def page_header():
    st.write("""
# Mit jDPG-Leitfäden chatten

Mit dieser App ist es möglich, Fragen über die Leitfäden der jDPG mittels KI beantworten zu lassen.
Dazu liest die App die Leitfäden ein und verwendet diese für kontextualisierte Antworten (Retrieval Augmented Generation,RAG).
Diese Anwendung verwendet das Modell `gpt-4o-mini` von OpenAI. 
Zur Identifizierung geeigeter Dokumente werden aus den Dokumenten sowie aus der Anfrage per KI Schlagworte genertiert (sparse embedding).

## Beispiel-Fragen
             
* Welche Aufgaben hat die jDPG und wie arbeitet sie mit der DPG zusammen?
* Wie kann ich Reisekosten für eine Veranstaltung der jDPG abrechnen?
* Nenne die Aufgaben der jDPG-Reginalgruppen.
             """)
    
def make_clickable(url):
    return f'<a href="{url}" target="_blank">Link</a>'

def main():
    page_header()
    with st.form(key="chat"):
        st.write("""
            ### Anfrage
            Diese Anfrage (Prompt) wird an das KI-Modell gesendet:
        """)
        prompt = st.text_input(label="Gib hier diene Anfrage ein")
        st.write("Die folgenden Parameter dienen der Konfiguration der Anfrage:")
        temperature = st.number_input(label="Temperatur (zwischen 0 und 1, höhere Werte für kreativere Antworten)", value=0.1, min_value=0.0, max_value=1.0)
        max_tokens = st.number_input(label="Maximale Anzahl an Antwort-Tokens", value=1000, min_value=100, max_value=10000)
        use_rag = st.checkbox(label="Ergebnis mittels Retrieval Augmented Generation (RAG) verbessern?", value=True)
        num_docs = st.number_input(label="Anzahl zu verwendender Dokumente (wenn RAG genutzt wird)", value=8, min_value=0, max_value=20)
        submit = st.form_submit_button(label="Absenden")

    if submit:
        generation_kwargs = {"temperature": temperature, "max_tokens": max_tokens}

        if use_rag:
            kws = get_keywords(generator, prompt).split(',')
            cur = conn.cursor()

            ids = []
            for kw in kws:
                cur.execute(f"SELECT id FROM documents WHERE keywords LIKE '%{kw}%' LIMIT 5")
                ids = ids + [i[0] for i in cur.fetchall()]

            bins = np.bincount(ids)
            n = np.arange(0, bins.shape[0])
            pairs = np.array([bins, n]).T

            idx = np.argsort(pairs[:,0])
            pairs = pairs[idx, :]
            relevant_pairs = list(pairs)[-num_docs:]

            matched_documents = [cur.execute(f"SELECT title, date, url FROM documents WHERE id={pair[1]}").fetchone() for pair in relevant_pairs]
            matched_documents.reverse()
            docs = pd.DataFrame({
                "Titel des Dokuments": [doc[0] for doc in matched_documents],
                "Veröffentlichungsdatum": [doc[1] for doc in matched_documents],
                "URL": [doc[2] for doc in matched_documents]
            })
            docs["Link"] = docs['URL'].apply(make_clickable)
            st.write("""
                     ## Relevante Dokumente:
                     Die folgenden Dokumente werden bei der Erstellung der Antwort berücksichtigt. 
                     Dabei sind die Dokumente von relevant zu weniger relevant sortiert.
                     """)
            st.markdown(docs[["Titel des Dokuments", "Veröffentlichungsdatum", "Link"]].to_html(escape=False), unsafe_allow_html=True)

            rag_request = """
            Beantworte die Frage am Ende mit Bezug auf den folgenden Kontext. 
            Erkläre deine Antwort ausführlich und nenne Dokumente, auf die du dich beziehst, mit Titel und Verabschiedungsdatum.
            Erstelle eine passende Überschrift für deine Antwort.\n\nKontext:\n\n"""
            for b, n in relevant_pairs:
                title, text = cur.execute(f"SELECT title, content FROM documents WHERE id={n}").fetchall()[0]
                rag_request = rag_request + "Title:" + title + "\n\nText:" + text + "\n\n"

            st.write("## RAG Ausgabe:")
            with st.spinner("Wird verarbeitet..."):
                st.write(generator.run(prompt=(rag_request+ "\n\nFrage:"  + prompt), generation_kwargs=generation_kwargs)["replies"][0])
        else:
            st.write("## Standard-Ausgabe:")
            with st.spinner("Wird verarbeitet..."):
                st.write(generator.run(prompt=prompt, generation_kwargs=generation_kwargs)["replies"][0])
       

if __name__ == "__main__":
    main()