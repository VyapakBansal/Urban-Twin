# Azure Terraform — Urban Twin demo VM

Default posture: `enable_demo_vm = false` → resource group + budget only.  
Set `enable_demo_vm = true` for a short demo, then **`terraform destroy`**.

## Cost rules (~$100 credits)

1. Budget alert emails in `terraform.tfvars` before first paid resource.
2. One **Standard_B2s** VM runs Docker PostGIS + Kafka + app processes + nginx.
3. Public ports: **22** (your IP only) and **80** (map). API/WS stay on localhost behind nginx.
4. Destroy after demos — idle VMs eat credits.

## Layout

| File | Purpose |
|---|---|
| `versions.tf` | `azurerm` provider |
| `variables.tf` | region, budget, VM, secrets |
| `main.tf` | resource group + monthly budget |
| `vm.tf` | VNet, NSG, public IP, Ubuntu VM + cloud-init |
| `outputs.tf` | HTTP URL, SSH command |
| `../deploy/*` | nginx, compose, bootstrap, cloud-init template |

## Apply

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit: subscription_id, ssh_public_key, allowed_ssh_cidr (/32),
#       budget_contact_emails, openweather_api_key, enable_demo_vm = true

az login
terraform init
terraform plan
terraform apply
```

After apply, wait 10–20 minutes for bootstrap:

```bash
terraform output demo_http_url
terraform output ssh_command
# ssh … then: sudo tail -f /var/log/urban-twin-bootstrap.log
curl "$(terraform output -raw demo_api_health_url)"
```

## Tear down

```bash
terraform destroy
```
