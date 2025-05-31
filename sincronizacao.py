import oci
import requests
import json
import csv
from datetime import datetime
from pathlib import Path

# --------------------------- CONFIG ---------------------------
config = oci.config.from_file() # Normalmente o padrão fica em "~/.oci/config", "DEFAULT"
FRESHSERVICE_DOMAIN = "https://[INSIRA SEU DOMINIO].freshservice.com" # Coloque o dominio da sua empresa. 
API_KEY = "API_KEY" # Insira a API KEY do Fresh Service. 
ASSET_TYPE_IDS = {
    "instance": XXXXXXXXX, # Extraia via API do Fresh qual os codigos de cada tipo de recurso. 
    "dbsystem": XXXXXXXX,
    "bucket": XXXXXXXXX,
    "vcn": XXXXXXXXXX,
    "subnet": XXXXXXXX,
    "load_balancer": XXXXXXXXX,
}
LOCATION_MAP = {"sa-saopaulo-1": XXXXXXX} #Extraia via API do Fresh qual o codigo da region cadastrada.
LOG_PATH = f"execucao_freshservice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# --------------------------- FUNÇÕES AUXILIARES ---------------------------
def carregar_departamentos_csv(path="departamentos.csv"):
    departamentos = {}
    with open(path, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            ocid = row["ocid_compartment"].strip()
            departamentos[ocid] = {
                "id": int(row["department_id"].strip()),
                "nome": row["nome_compartimento"].strip(),
                "criticidade": row.get("criticidade", "").strip(),
                "responsavel": row.get("responsavel", "").strip()
            }
    return departamentos

def salvar_json_log(nome, dados):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    Path("logs").mkdir(exist_ok=True)
    with open(f"logs/{nome}_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

def salvar_csv_por_departamento(relatorios):
    Path("relatorios").mkdir(exist_ok=True)
    for dep_id, linhas in relatorios.items():
        nome_arquivo = f"relatorios/relatorio_dep_{dep_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(nome_arquivo, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Tipo", "Nome", "Ação", "Campos Modificados"])
            writer.writerows(linhas)

def baixar_todos_ativos_freshservice():
    ativos = []
    page = 1
    while True:
        url = f"{FRESHSERVICE_DOMAIN}/api/v2/assets?page={page}&per_page=100"
        r = requests.get(url, auth=(API_KEY, "X"), headers={"Content-Type": "application/json"})
        if r.status_code != 200:
            print(f"Erro ao buscar página {page}: {r.status_code}")
            break
        dados = r.json().get("assets", [])
        if not dados:
            break
        ativos.extend(dados)
        page += 1
    return ativos

def remover_campos_none(payload):
    return {k: v for k, v in payload.items() if v is not None}

# --------------------------- COMPARAÇÃO E ATUALIZAÇÃO ---------------------------
def comparar_e_sincronizar(tipo, ativos_fresh, recursos_oci, departamentos_txt, relatorios):
    atualizacoes = []
    criacoes = []

    for nome, recurso in recursos_oci.items():
        dep = departamentos_txt.get(recurso["compartment_id"])
        if not dep:
            print(f"[AVISO] Compartment sem mapeamento: {recurso['compartment_id']}")
            continue

        location_id = LOCATION_MAP.get(recurso.get("region", "sa-saopaulo-1"), 6000199993)

        esperado = {
            "name": recurso["name"],
            "asset_type_id": ASSET_TYPE_IDS[tipo],
            "department_id": dep["id"],
            "location_id": location_id,
            "impact": dep.get("criticidade"),
            "user_id": int(dep["responsavel"]) if dep.get("responsavel") else None,
            "description": f"{tipo.capitalize()} criado automaticamente. OCID: {recurso['ocid']}",
            "usage_type": "permanent"
        }

        encontrado = next(
            (a for a in ativos_fresh.values()
             if a.get("name", "").strip().lower() == nome.lower()
             and str(a.get("department_id")) == str(dep["id"])),
            None
        )
        if encontrado:
            diff = {}
            for campo in ["department_id", "impact", "location_id"]:
                if str(encontrado.get(campo)) != str(esperado[campo]):
                    diff[campo] = esperado[campo]
            if encontrado.get("user_id") != esperado["user_id"]:
                diff["user_id"] = esperado["user_id"]
            if diff:
                print(f"[ALTERAÇÃO] {nome} ({tipo}) precisa de atualização:")
                for k, v in diff.items():
                    print(f"  - {k}: novo valor -> {v}")
                atualizacoes.append((encontrado.get("display_id"), nome, {**diff, "description": esperado["description"]}, dep["id"]))
        else:
            criacoes.append((remover_campos_none(esperado), dep["id"]))

    print(f"[{tipo.upper()}] Atualizações: {len(atualizacoes)} | Criações: {len(criacoes)}")
    confirma = input(f"Deseja aplicar alterações para {tipo.upper()}? (s/N): ").strip().lower()
    if confirma != "s":
        print("[ABORTADO] Nenhuma modificação aplicada.")
        return

    for display_id, nome, campos, dep_id in atualizacoes:
        payload = {"asset": remover_campos_none(campos)}
        url = f"{FRESHSERVICE_DOMAIN}/api/v2/assets/{display_id}"
        r = requests.put(url, auth=(API_KEY, "X"), headers={"Content-Type": "application/json"}, data=json.dumps(payload))
        if r.status_code == 200:
            print(f"✅ Atualizado: {nome}")
            relatorios[dep_id].append([tipo, nome, "Atualizado", json.dumps(campos)])
        else:
            print(f"❌ Falha ao atualizar {nome} (ID: {display_id}): {r.status_code} - {r.text}")

    for novo, dep_id in criacoes:
        payload = {"asset": novo}
        url = f"{FRESHSERVICE_DOMAIN}/api/v2/assets"
        r = requests.post(url, auth=(API_KEY, "X"), headers={"Content-Type": "application/json"}, data=json.dumps(payload))
        if r.status_code in [200, 201]:
            asset_id = r.json().get("asset", {}).get("asset_tag")
            print(f"🆕 Criado: {novo['name']} (ID: {asset_id})")
            relatorios[dep_id].append([tipo, novo['name'], "Criado", json.dumps(novo)])
        else:
            print(f"❌ Falha ao criar {novo['name']}: {r.status_code} - {r.text}")

# --------------------------- EXECUÇÃO PRINCIPAL ---------------------------
if __name__ == "__main__":
    from collections import defaultdict

    print("[INFO] Carregando departamentos...")
    departamentos_txt = carregar_departamentos_csv()

    print("[INFO] Baixando ativos do Freshservice...")
    todos_ativos_fresh = baixar_todos_ativos_freshservice()
    salvar_json_log("freshservice_ativos", todos_ativos_fresh)

    ativos_filtrados = {}
    for asset in todos_ativos_fresh:
        nome = asset.get("name", "").strip().lower()
        if nome:
            ativos_filtrados[nome] = asset

    print("[INFO] Carregando recursos da OCI...")
    identity = oci.identity.IdentityClient(config)
    compartments = identity.list_compartments(config["tenancy"], compartment_id_in_subtree=True).data
    compartments.append(identity.get_compartment(config["tenancy"]).data)

    compartments_ocids = [c.id for c in compartments]
    nao_mapeados = set(departamentos_txt.keys()) - set(compartments_ocids)
    if nao_mapeados:
        print("[ALERTA] Compartimentos no CSV que não existem na OCI:")
        for ocid in nao_mapeados:
            print(f" - {ocid} ({departamentos_txt[ocid]['nome']})")
    else:
        print("[OK] Todos os compartimentos do CSV foram encontrados na OCI.")

    compartment_ids = [c.id for c in compartments if c.id in departamentos_txt]

    compute = oci.core.ComputeClient(config)
    db = oci.database.DatabaseClient(config)
    object_storage = oci.object_storage.ObjectStorageClient(config)
    network = oci.core.VirtualNetworkClient(config)
    lb = oci.load_balancer.LoadBalancerClient(config)

    from collections import defaultdict
    recursos = defaultdict(dict)

    for cid in compartment_ids:
        for i in compute.list_instances(cid).data:
            recursos["instance"][i.display_name.strip().lower()] = {"name": i.display_name.strip(), "ocid": i.id, "compartment_id": i.compartment_id, "region": config["region"]}
        for i in db.list_db_systems(cid).data:
            recursos["dbsystem"][i.display_name.strip().lower()] = {"name": i.display_name.strip(), "ocid": i.id, "compartment_id": i.compartment_id, "region": config["region"]}
        for i in object_storage.list_buckets(config["tenancy"], cid).data:
            recursos["bucket"][i.name.strip().lower()] = {"name": i.name.strip(), "ocid": i.id, "compartment_id": cid, "region": config["region"]}
        for i in network.list_vcns(cid).data:
            recursos["vcn"][i.display_name.strip().lower()] = {"name": i.display_name.strip(), "ocid": i.id, "compartment_id": i.compartment_id, "region": config["region"]}
        for i in network.list_subnets(cid).data:
            recursos["subnet"][i.display_name.strip().lower()] = {"name": i.display_name.strip(), "ocid": i.id, "compartment_id": i.compartment_id, "region": config["region"]}
        for i in lb.list_load_balancers(cid).data:
            recursos["load_balancer"][i.display_name.strip().lower()] = {"name": i.display_name.strip(), "ocid": i.id, "compartment_id": i.compartment_id, "region": config["region"]}

    relatorios = defaultdict(list)
    for tipo, dados in recursos.items():
        comparar_e_sincronizar(tipo, ativos_filtrados, dados, departamentos_txt, relatorios)

    salvar_csv_por_departamento(relatorios)
    print("[FINALIZADO] Processamento completo. Relatórios salvos.")
