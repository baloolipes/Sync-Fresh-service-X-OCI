# Sync-Fresh-service-X-OCI

Este projeto tem como objetivo realizar a **sincronização automática de ativos** da Oracle Cloud Infrastructure (OCI) com o inventário de ativos do **Freshservice**, validando e atualizando os registros conforme necessário.

## ✨ Funcionalidades

- Coleta automática de recursos da OCI:
  - Compute Instances
  - DB Systems (DBaaS)
  - Buckets (Object Storage)
  - VCNs
  - Subnets
  - Load Balancers
- Sincronização com base em:
  - Nome do recurso
  - Departamento (via Compartment OCID → department_id)
- Atualizações de ativos existentes no Freshservice
- Criação de novos ativos com campos padronizados
- Geração de relatório CSV por departamento
- Validação visual no terminal antes de aplicar as modificações

## 📁 Estrutura esperada

- `departamentos.csv`: define os mapeamentos entre Compartimentos da OCI e Departamentos do Freshservice.
- `sincronizacao.py`: script principal de sincronização.
- `logs/`: diretório onde são salvos arquivos de log JSON com os dados brutos.
- `relatorios/`: relatórios CSV com detalhes de alterações/criações por departamento.

## 🛠️ Pré-requisitos

- Python 3.8+
- Dependências:
  ```bash
  pip install oci requests

Configuração do OCI CLI:
Arquivo de configuração ~/.oci/config com o perfil "DEFAULT" devidamente autenticado (tenancy, user, fingerprint, key_file e region)

Freshservice:
Token de API válido (Classic API Key)
Permissões suficientes para ler e atualizar ativos (Assets)

