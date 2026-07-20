# Azure Terraform — Week 4

**Do not `terraform apply` until the local pipeline is stable and you are ready to spend credits.**

Default posture: write config → `terraform init` → `terraform plan` → stop.  
`apply` only for a short demo window, then `terraform destroy`.

## Cost rules (~$100 Azure credits)

1. Set a **budget alert** first (included in this stack; `enable_demo_vm` defaults to **false**).
2. Prefer **one small demo VM** over many always-on PaaS SKUs when you do apply.
3. Destroy the resource group after demos — idle VMs eat credits quietly.
4. Keep Postgres/Kafka on the VM via Docker Compose (same as local) to avoid paying for Event Hubs + Flexible Server during learning.

## Layout

| File | Purpose |
|---|---|
| `versions.tf` / `providers.tf` | `azurerm` provider |
| `variables.tf` | region, names, budget, VM toggle |
| `main.tf` | resource group + monthly budget + alert |
| `vm.tf` | optional Ubuntu VM (`enable_demo_vm`) |
| `outputs.tf` | useful IDs / IPs |
| `terraform.tfvars.example` | copy → `terraform.tfvars` (gitignored) |

## Commands (you run)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit subscription_id, and keep enable_demo_vm = false for plan-only learning

az login          # Azure CLI
terraform init
terraform plan    # safe — shows what would be created; $0 if you don't apply
```

Only when demo day:

```bash
# in terraform.tfvars: enable_demo_vm = true
terraform apply
# … demo …
terraform destroy
```

## After a VM exists

SSH in, install Docker, clone the repo, run `docker compose up -d`, start Python services (or a Compose file that includes them later). Point a DNS/firewall rule only as needed; do not leave SSH open to the world longer than the demo.
