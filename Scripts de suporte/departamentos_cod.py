#Script para consultar e extrair todos os codigos dos departamentos existentes no FreshService. 
import requests
from requests.auth import HTTPBasicAuth

# === CONFIGURAÇÕES ===
FRESHSERVICE_DOMAIN = "[DOMINIO].freshservice.com"  # Substitua se for diferente
FRESHSERVICE_API_KEY = "[API_KEY]"  # Substitua pela sua chave real

# === VARIÁVEIS ===
url = f"https://{FRESHSERVICE_DOMAIN}/api/v2/asset_types"
auth = HTTPBasicAuth(FRESHSERVICE_API_KEY, "X")
params = {"page": 1, "per_page": 100}  # Ajustar para trazer mais por página
headers = {"Content-Type": "application/json"}

all_asset_types = []

while True:
    response = requests.get(url, auth=auth, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Erro ao buscar tipos de ativos: {response.status_code} - {response.text}")
        break

    data = response.json()
    asset_types = data.get("asset_types", [])
    if not asset_types:
        break

    all_asset_types.extend(asset_types)

    # Verifica se ainda há mais páginas
    if len(asset_types) < params["per_page"]:
        break

    params["page"] += 1  # próxima página

# === SALVAR EM TXT ===
with open("asset_types.txt", "w", encoding="utf-8") as f:
    for asset_type in all_asset_types:
        f.write(f"{asset_type['id']} - {asset_type['name']}\n")

print(f"Total de tipos de ativos encontrados: {len(all_asset_types)}")
print("Dados salvos em asset_types.txt")
