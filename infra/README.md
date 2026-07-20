# Azure + Terraform — Urban Twin demo VM

You own the Azure account and the `apply` / `destroy` buttons. This file is the checklist.

**Default:** `enable_demo_vm = false` → resource group (+ optional budget) only.  
**Demo day:** set `enable_demo_vm = true`, apply, show the map, then **destroy**.

## What gets created

| Resource | Purpose |
|---|---|
| Resource group `rg-urbantwin-demo` | Container for everything |
| Optional subscription budget | Email alerts (if emails set) |
| VNet + subnet + NSG | Network; **SSH :22** from your IP only; **HTTP :80** public |
| Public IP + NIC + **Standard_B2s** Ubuntu 22.04 | Runs Docker PostGIS/Kafka + Python apps + nginx |
| cloud-init | Clones GitHub repo, runs [deploy/azure-bootstrap.sh](../deploy/azure-bootstrap.sh) |

Public surface: **port 80 only** (map + `/api/*` + `/ws/*`). Postgres/Kafka/API/WS stay on localhost on the VM.

## Cost rules (~$100 student credits)

1. Set a Portal budget **or** `budget_contact_emails` in tfvars before first paid VM.
2. One B2s is enough — do not add Event Hubs / Flexible Server for this demo.
3. Idle VMs burn credits — `terraform destroy` after the interview/demo.
4. Region default: `canadacentral`.

---

## Portal steps (before or alongside Terraform)

1. Open [Azure Portal](https://portal.azure.com) → pick **Azure for Students** (or your chosen subscription).
2. **Subscriptions** → copy **Subscription ID**.
3. **Cost Management + Billing** → **Budgets** → create monthly budget (e.g. $40) with email alerts at 50% / 90%.
4. You do **not** need to create a VM in the Portal — Terraform does that.
5. After destroy, confirm the resource group is gone under **Resource groups**.

---

## CLI + Terraform steps

### 1. Login and select subscription

```bash
az login
az account set --subscription 700f4313-555b-46ef-bef2-018bbbcb192d
# or: az account set --subscription "Azure for Students"
az account show --query "{name:name,id:id}" -o table
```

### 2. Collect values for tfvars

```bash
# Subscription ID
az account show --query id -o tsv

# Your public IP (for SSH lockdown)
curl -s https://api.ipify.org
echo

# SSH public key (one line)
# Windows Git Bash:
cat ~/.ssh/id_ed25519.pub
```

OpenWeather key: same value as in local `.env` (`OPENWEATHER_API_KEY`).

### 3. Write `terraform.tfvars` (gitignored)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit with your editor
```

Minimum fields:

```hcl
subscription_id       = "700f4313-555b-46ef-bef2-018bbbcb192d"
enable_demo_vm        = true
ssh_public_key        = "ssh-ed25519 AAAA... yourkey"
allowed_ssh_cidr      = "YOUR.PUBLIC.IP/32"
openweather_api_key   = "your-openweather-key"
budget_contact_emails = ["you@example.com"]   # recommended
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

# Wait 10–20 minutes for first boot (Docker, OSM, model train)
curl "$(terraform output -raw demo_api_health_url)"
# Browser → demo_http_url

# If something stuck:
# ssh urbanadmin@<ip>
# sudo tail -f /var/log/urban-twin-bootstrap.log
```

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
| `az login` MFA / wrong tenant | `az login --tenant <university-tenant-id>` then `az account set` |
| SSH timeout | `allowed_ssh_cidr` must be your **current** public `/32` |
| Map 502 / empty | Bootstrap still running — watch `/var/log/urban-twin-bootstrap.log` |
| Weather missing | `openweather_api_key` empty in tfvars / `/etc/urban-twin.env` on VM |
| Credits surprise | Destroy RG; confirm no leftover disks/IPs in Portal |
