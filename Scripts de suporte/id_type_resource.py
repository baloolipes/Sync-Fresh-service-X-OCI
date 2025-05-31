import oci
import requests
import json
import csv
from datetime import datetime

# --------------------------- CONFIGURAÇÕES ---------------------------
config = oci.config.from_file("~/.oci/config", "DEFAULT")
FRESHSERVICE_DOMAIN = "https://[dominio].freshservice.com"
API_KEY = "API_KEY"
HEADERS = {
    "Content-Type": "application/json"
}
ASSET_TYPE_ID = 6000871762  # Instances
OCID_CUSTOM_FIELD = "ocid_6000871762"
LOCATION_MAP = {
    "sa-saopaulo-1": 6000199993
}
LOG_PATH = "erros_execucao_freshservice.log"

# --------------------------- FUNÇÕES AUXILIARES ---------------------------
def carregar_departamentos_csv(path="departamentos.csv"):
    departamentos = {}
    with open(path, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            ocid = row["ocid_compartment"].strip()
            departamentos[ocid] = {
                "id": int(row["department_id"].strip()),
                "nome": row["nome_compartimento"].strip()
            }
    return departamentos

def ativo_existe_por_nome(nome):
    url = f"{FRESHSERVICE_DOMAIN}/api/v2/assets"
    page = 1
    while True:
        r = requests.get(url, auth=(API_KEY, "X"), headers=HEADERS, params={"page": page})
        try:
            assets = r.json().get("assets", [])
        except json.JSONDecodeError:
            return None
        for asset in assets:
            if asset.get("name", "").strip().lower() == nome.strip().lower():
                return asset["id"]
        if not assets:
            break
        page += 1
    return None

def criar_ou_atualizar_ativo(name, ocid, department_id, location_id, erros_log):
    payload = {
        "asset": {
            "name": name,
            "asset_type_id": ASSET_TYPE_ID,
            "department_id": department_id,
            "location_id": location_id,
            "custom_fields": {
                OCID_CUSTOM_FIELD: ocid
            }
        }
    }

    asset_id = ativo_existe_por_nome(name)
    if asset_id:
        url = f"{FRESHSERVICE_DOMAIN}/api/v2/assets/{asset_id}"
        metodo = requests.put
        acao = "Atualizado"
    else:
        url = f"{FRESHSERVICE_DOMAIN}/api/v2/assets"
        metodo = requests.post
        acao = "Criado"

    r = metodo(url, auth=(API_KEY, "X"), headers=HEADERS, data=json.dumps(payload))
    if r.status_code in [200, 201]:
        print(f"✅ {acao} ativo: {name}")
    else:
        erro = f"❌ Erro ao {acao.lower()} ativo {name}: {r.status_code} - {r.text}"
        print(erro)
        erros_log.append({"instancia": name, "motivo": erro})

    return r.status_code, r.text

def salvar_log_erros(erros):
    log_content = f"Relatório de erros - Execução em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    for erro in erros:
        log_content += f"[INSTÂNCIA] {erro['instancia']}\n[ERRO] {erro['motivo']}\n\n"
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(log_content)

# --------------------------- EXECUÇÃO PRINCIPAL ---------------------------
if __name__ == "__main__":
    compute_client = oci.core.ComputeClient(config)
    identity_client = oci.identity.IdentityClient(config)

    erros_log = []
    departamentos_txt = carregar_departamentos_csv("departamentos.csv")

    tenancy_ocid = config["tenancy"]
    response = identity_client.list_compartments(tenancy_ocid, compartment_id_in_subtree=True)
    compartments = response.data
    root_compartment = identity_client.get_compartment(tenancy_ocid).data
    compartments.append(root_compartment)

    for compartment in compartments:
        list_instances = compute_client.list_instances(compartment.id).data

        for instance in list_instances:
            instance_name = instance.display_name
            ocid = instance.id
            compartment_id = instance.compartment_id
            region = config["region"]

            print(f"\n[DEBUG] Processando instância: {instance_name}")
            print(f"[DEBUG] OCID capturado da instância: {ocid}")
            print(f"[DEBUG] Compartment OCID: {compartment_id}")
            print(f"[DEBUG] Região: {region}")

            department_id = departamentos_txt.get(compartment_id, {}).get("id")
            if not department_id:
                aviso = f"Departamento não encontrado para o compartimento: {compartment_id}"
                print(f"⚠️  {aviso}")
                erros_log.append({"instancia": instance_name, "motivo": aviso})
                continue

            location_id = LOCATION_MAP.get(region)

            status_code, resposta = criar_ou_atualizar_ativo(
                name=instance_name,
                ocid=ocid,
                department_id=department_id,
                location_id=location_id,
                erros_log=erros_log
            )

    salvar_log_erros(erros_log)
