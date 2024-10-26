# RAG für ZaPF und jDPG Beschlüsse

Kurzanleitung zum Deployment der App:

* Python (<=3.11) mit installierten Requirements
* Azure OpenAI Service
* Azure App Service Plan für Web App

## Lokal starten:

```bash
export AZURE_OPENAI_API_KEY=<YOUR API KEY>

python -m streamlit run main-jdpg.py #bzw
python -m streamlit run main-zapf.py
```
im jeweiligen Verzeichnis unter `./environments`

## Deployment in Azure

On the webapp, the environment variable `AZURE_OPENAI_API_KEY` to your API key. This can be done through the Azure Portal or az cli.

**Commands for deploying the app:**

```bash
az webapp up --name <WEB APP NAME> --plan <ASP NAME> --sku B1 --resource-group <RG NAME> --runtime "PYTHON|3.11" --location WestEurope

az webapp config set --resource-group <RG NAME> --name <WEB APP NAME> --startup-file "streamlit run main-<ENVIRONMENT>.py --server.port=8000 --server.address=0.0.0.0"
```

Location and SKU can be changed as needed

