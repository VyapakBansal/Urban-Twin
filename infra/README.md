# Azure + Terraform — Urban Twin demo VM

This directory provisions an optional Azure demo host. The default is **no VM** (`enable_demo_vm = false`); turn it on for a short-lived public demo, then destroy.

**Default:** resource group (+ optional budget) only.  
**Demo:** set `enable_demo_vm = true`, apply, use the map, then **`terraform destroy`**.

## What gets created

| Resource | Purpose |
|---|---|
| Resource group `rg-urbantwin-demo` | Container for everything |
| Optional subscription budget | Email alerts (if emails set) |
| VNet + subnet + NSG | Network; **SSH :22** from your IP only; **HTTP :80** public |
| Public IP + NIC + **Standard_B2s** Ubuntu 22.04 | Runs Docker PostGIS/Kafka + Python apps + nginx |
| cloud-init | Clones the GitHub repo, runs [deploy/azure-bootstrap.sh](../deploy/azure-bootstrap.sh) |

Public surface: **port 80 only** (map + `/api/*` + `/ws/*`). Postgres, Kafka, API, and the WebSocket bridge stay on localhost on the VM.

## Cost guidelines

1. Set a Portal budget **or** `budget_contact_emails` in tfvars before the first paid VM.
2. One B2s is enough — do not add Event Hubs / Flexible Server for this demo.
3. Idle VMs cost money — `terraform destroy` when finished.
4. Region default: `canadacentral`.

---

## Portal steps

1. Open [Azure Portal](https://portal.azure.com) → select the subscription.
2. **Subscriptions** → copy **Subscription ID**.
3. **Cost Management + Billing** → **Budgets** → create a monthly budget with email alerts (e.g. 50% / 90%).
4. Terraform creates the VM — no need to create one in the Portal.
5. After destroy, confirm the resource group is gone under **Resource groups**.

---

## CLI + Terraform

### 1. Login and select subscription

```bash
az login
az account set --subscription "<subscription-id>"
az account show --query "{name:name,id:id}" -o table
```

### 2. Collect values for tfvars

```bash
az account show --query id -o tsv
curl -s https://api.ipify.org && echo
cat ~/.ssh/id_ed25519.pub
```

OpenWeather key: same value as local `.env` (`OPENWEATHER_API_KEY`).

### 3. Write `terraform.tfvars` (gitignored)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Minimum fields:

```hcl
subscription_id       = "<subscription-id>"
enable_demo_vm        = true
ssh_public_key        = "ssh-ed25519 AAAA... yourkey"
allowed_ssh_cidr      = "YOUR.PUBLIC.IP/32"
openweather_api_key   = "your-openweather-key"
budget_contact_emails = ["you@example.com"]
git_repo_url          = "https://github.com/VyapakBansal/Urban-Twin.git"
git_branch            = "main"
```

### 4. Plan and apply

```bash
terraform init
terraform plan
terraform apply
```

### 5. Verify

```bash
terraform output demo_http_url
terraform output demo_api_health_url
terraform output ssh_command

# First boot can take 10–20 minutes (Docker, OSM, model train)
curl "$(terraform output -raw demo_api_health_url)"
```

Bootstrap log on the VM: `/var/log/urban-twin-bootstrap.log`.

### 6. Tear down

```bash
terraform destroy
```

Portal backup: delete resource group `rg-urbantwin-demo`.

---

## File map

| File | Role |
|---|---|
| `versions.tf` | azurerm provider |
| `variables.tf` | inputs (secrets marked sensitive) |
| `main.tf` | resource group + budget |
| `vm.tf` | network + VM + cloud-init |
| `outputs.tf` | URLs / SSH |
| `../deploy/*` | nginx, compose, bootstrap script, cloud-init template |

## Troubleshooting

| Symptom | Check |
|---|---|
| `az login` MFA / wrong tenant | `az login --tenant <tenant-id>` then `az account set` |
| SSH timeout | `allowed_ssh_cidr` must be the current public `/32` |
| Map 502 / empty | Bootstrap still running — watch `/var/log/urban-twin-bootstrap.log` |
| Weather missing | `openweather_api_key` empty in tfvars / `/etc/urban-twin.env` on VM |
| Unexpected cost | Destroy RG; confirm no leftover disks/IPs in Portal |
